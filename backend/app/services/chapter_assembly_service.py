from __future__ import annotations

from datetime import datetime
from typing import Any

from backend.app.core.paths import AppPaths
from backend.app.domain.models.common import utc_now
from backend.app.domain.models.issues import ChapterCheckReport
from backend.app.domain.models.planning import ChapterPlan, ScenePlan, VolumePlan
from backend.app.domain.models.writing import (
    ChapterAssembledDocument,
    ChapterAssembledSourceVersions,
    ChapterBasicStats,
    ChapterSceneOrderItem,
    SceneDraft,
)
from backend.app.repositories.file_repository import FileRepository
from backend.app.repositories.sqlite_repository import SQLiteRepository
from backend.app.services.chapter_checks_service import ChapterChecksService
from backend.app.services.exceptions import ConflictError
from backend.app.services.memory_service import MemoryService
from backend.app.services.planner_service import PlannerService
from backend.app.services.scene_draft_service import SceneDraftService


class ChapterAssemblyService:
    def __init__(
        self,
        paths: AppPaths,
        file_repository: FileRepository,
        sqlite_repository: SQLiteRepository,
        planner_service: PlannerService,
        draft_service: SceneDraftService,
        memory_service: MemoryService,
        chapter_checks_service: ChapterChecksService,
    ) -> None:
        self.paths = paths
        self.file_repository = file_repository
        self.sqlite_repository = sqlite_repository
        self.planner_service = planner_service
        self.draft_service = draft_service
        self.memory_service = memory_service
        self.chapter_checks_service = chapter_checks_service

    def assemble(self, project_id: str, chapter_id: str) -> ChapterAssembledDocument:
        project = self._require_project(project_id)
        slug = project["slug"]
        volume, chapter, scenes = self._load_ready_plans(project_id, chapter_id)
        accepted_by_scene = self._collect_unique_active_accepted(project_id, slug, scenes, strict=True)

        content_md = "\n\n".join(accepted_by_scene[scene.scene_id].content_md.strip() for scene in scenes)
        existing = self._read_assembled(slug, chapter_id)
        next_version = 1 if existing is None else existing.version + 1
        now = utc_now()
        assembled = ChapterAssembledDocument(
            project_id=project_id,
            volume_id=volume.volume_id,
            chapter_id=chapter.chapter_id,
            chapter_no=chapter.chapter_no,
            version=next_version,
            status="assembled",
            updated_at=now,
            source_versions=ChapterAssembledSourceVersions(
                volume_version=volume.version,
                chapter_version=chapter.version,
                scene_versions={scene.scene_id: scene.version for scene in scenes},
                accepted_draft_ids={scene.scene_id: accepted_by_scene[scene.scene_id].draft_id for scene in scenes},
            ),
            scene_order=[
                ChapterSceneOrderItem(
                    scene_id=scene.scene_id,
                    scene_no=scene.scene_no,
                    accepted_draft_id=accepted_by_scene[scene.scene_id].draft_id,
                )
                for scene in scenes
            ],
            content_md=content_md,
            summary=self._build_summary(scenes, accepted_by_scene),
            hook=self._build_hook(chapter, scenes, accepted_by_scene),
            basic_stats=self._build_basic_stats(scenes, accepted_by_scene, content_md),
            latest_check_report_path=self.paths.relative_to_project(slug, self.paths.chapter_check_latest_path(slug, chapter.chapter_id)),
            last_check_status=None,
            last_check_blocker_count=0,
            last_check_warning_count=0,
            finalized_at=None,
            finalized_from_assembly_version=None,
        )
        self._write_assembled(slug, assembled)
        self.chapter_checks_service.run_for_chapter(project_id, assembled, trigger="assemble_auto")
        return self.get_assembled(project_id, chapter_id)

    def get_assembled(self, project_id: str, chapter_id: str) -> ChapterAssembledDocument:
        project = self._require_project(project_id)
        slug = project["slug"]
        assembled = self._read_assembled(slug, chapter_id)
        if assembled is None:
            raise KeyError(chapter_id)
        return self._refresh_stale_status(project_id, slug, assembled)

    def recheck(self, project_id: str, chapter_id: str) -> ChapterCheckReport:
        assembled = self.get_assembled(project_id, chapter_id)
        return self.chapter_checks_service.run_for_chapter(project_id, assembled, trigger="manual_recheck")

    def get_latest_report(self, project_id: str, chapter_id: str) -> ChapterCheckReport | None:
        return self.chapter_checks_service.get_latest_report(project_id, chapter_id)

    def finalize(self, project_id: str, chapter_id: str) -> ChapterAssembledDocument:
        project = self._require_project(project_id)
        slug = project["slug"]
        assembled = self.get_assembled(project_id, chapter_id)
        if assembled.status == "stale":
            raise ConflictError("Stale chapter must be re-assembled before finalize.")
        if assembled.status == "finalized":
            return assembled

        report = self.chapter_checks_service.ensure_finalize_allowed(project_id, assembled)
        assembled = self.get_assembled(project_id, chapter_id)
        if report.overall_status in {"blocked", "error"}:
            raise ConflictError("Chapter finalize blocked by latest chapter checks.")
        if assembled.status == "stale":
            raise ConflictError("Stale chapter must be re-assembled before finalize.")

        assembled.status = "finalized"
        assembled.finalized_at = utc_now()
        assembled.finalized_from_assembly_version = assembled.version
        self._write_assembled(slug, assembled)
        self.memory_service.update_finalized_chapter_summary(slug, assembled)
        return self.get_assembled(project_id, chapter_id)

    def _refresh_stale_status(self, project_id: str, slug: str, assembled: ChapterAssembledDocument) -> ChapterAssembledDocument:
        volume = self.planner_service.get_volume(project_id, assembled.volume_id)
        chapter = self.planner_service.get_chapter(project_id, assembled.chapter_id)
        scenes = self.planner_service.list_scenes(project_id, assembled.chapter_id)
        stale = False
        if volume.version != assembled.source_versions.volume_version:
            stale = True
        if chapter.version != assembled.source_versions.chapter_version:
            stale = True
        current_scene_versions = {scene.scene_id: scene.version for scene in scenes}
        if current_scene_versions != assembled.source_versions.scene_versions:
            stale = True
        current_order = [(scene.scene_id, scene.scene_no) for scene in sorted(scenes, key=lambda item: item.scene_no)]
        stored_order = [(item.scene_id, item.scene_no) for item in assembled.scene_order]
        if current_order != stored_order:
            stale = True
        current_accepted_ids = self._collect_current_accepted_ids(project_id, slug, scenes)
        if current_accepted_ids != assembled.source_versions.accepted_draft_ids:
            stale = True
        if stale and assembled.status != "stale":
            assembled.status = "stale"
            assembled.updated_at = utc_now()
            self._write_assembled(slug, assembled)
        return assembled

    def _load_ready_plans(self, project_id: str, chapter_id: str) -> tuple[VolumePlan, ChapterPlan, list[ScenePlan]]:
        chapter = self.planner_service.get_chapter(project_id, chapter_id)
        volume = self.planner_service.get_volume(project_id, chapter.volume_id)
        if volume.status != "ready":
            raise ConflictError("Volume must be ready before assembling chapter.")
        if chapter.status != "ready":
            raise ConflictError("Chapter must be ready before assembling chapter.")
        scenes = sorted(self.planner_service.list_scenes(project_id, chapter_id), key=lambda item: item.scene_no)
        if not scenes:
            raise ConflictError("Chapter has no planned scenes.")
        not_ready = [scene.scene_id for scene in scenes if scene.status != "ready"]
        if not_ready:
            raise ConflictError("All planned scenes must be ready before assembling chapter.")
        return volume, chapter, scenes

    def _collect_unique_active_accepted(
        self,
        project_id: str,
        slug: str,
        scenes: list[ScenePlan],
        *,
        strict: bool,
    ) -> dict[str, SceneDraft]:
        accepted_by_scene: dict[str, SceneDraft] = {}
        for scene in scenes:
            accepted_drafts = self._accepted_drafts_for_scene(project_id, slug, scene.scene_id)
            if len(accepted_drafts) > 1:
                if strict:
                    raise ConflictError("Scene contains multiple active accepted drafts.")
                continue
            if len(accepted_drafts) == 0:
                if strict:
                    raise ConflictError("All chapter scenes must have exactly one active accepted draft.")
                continue
            accepted_by_scene[scene.scene_id] = accepted_drafts[0]
        if strict and len(accepted_by_scene) != len(scenes):
            raise ConflictError("All chapter scenes must have exactly one active accepted draft.")
        return accepted_by_scene

    def _collect_current_accepted_ids(self, project_id: str, slug: str, scenes: list[ScenePlan]) -> dict[str, str]:
        accepted_by_scene = self._collect_unique_active_accepted(project_id, slug, scenes, strict=False)
        return {scene_id: draft.draft_id for scene_id, draft in accepted_by_scene.items()}

    def _accepted_drafts_for_scene(self, project_id: str, slug: str, scene_id: str) -> list[SceneDraft]:
        scene_dir = self.paths.scene_drafts_dir(slug, scene_id)
        if not scene_dir.exists():
            return []
        accepted_drafts: list[SceneDraft] = []
        for draft_path in sorted(scene_dir.glob("draft-*.json")):
            draft = SceneDraft.model_validate(self.file_repository.read_json(draft_path))
            if draft.project_id == project_id and draft.status == "accepted":
                accepted_drafts.append(draft)
        return accepted_drafts

    def _build_summary(self, scenes: list[ScenePlan], accepted_by_scene: dict[str, SceneDraft]) -> str:
        parts: list[str] = []
        for scene in scenes[:3]:
            draft = accepted_by_scene[scene.scene_id]
            piece = draft.summary.strip() or f"{scene.goal} -> {scene.outcome}"
            if piece:
                parts.append(f"{scene.title}：{piece}")
        return " ".join(parts).strip()

    def _build_hook(self, chapter: ChapterPlan, scenes: list[ScenePlan], accepted_by_scene: dict[str, SceneDraft]) -> str:
        if chapter.hook.strip():
            return chapter.hook.strip()
        last_scene = scenes[-1]
        if last_scene.outcome.strip():
            return last_scene.outcome.strip()
        return accepted_by_scene[last_scene.scene_id].summary.strip()

    def _build_basic_stats(self, scenes: list[ScenePlan], accepted_by_scene: dict[str, SceneDraft], content_md: str) -> ChapterBasicStats:
        paragraphs = self._paragraphs(content_md)
        characters = set()
        for scene in scenes:
            characters.update(scene.character_ids)
        char_count = len("".join(content_md.split()))
        return ChapterBasicStats(
            scene_count=len(scenes),
            accepted_scene_count=len(accepted_by_scene),
            character_count=len(characters),
            paragraph_count=len(paragraphs),
            char_count=char_count,
        )

    def _paragraphs(self, content_md: str) -> list[str]:
        normalized = content_md.replace("\r\n", "\n")
        blocks = [block.strip() for block in normalized.split("\n\n")]
        return [block for block in blocks if block]

    def _read_assembled(self, slug: str, chapter_id: str) -> ChapterAssembledDocument | None:
        path = self.paths.chapter_assembled_path(slug, chapter_id)
        if not self.file_repository.exists(path):
            return None
        return ChapterAssembledDocument.model_validate(self.file_repository.read_json(path))

    def _write_assembled(self, slug: str, assembled: ChapterAssembledDocument) -> None:
        self.file_repository.write_json(self.paths.chapter_assembled_path(slug, assembled.chapter_id), assembled.model_dump(mode="json"))

    def _require_project(self, project_id: str) -> dict[str, Any]:
        project = self.sqlite_repository.get_project_record(project_id)
        if project is None:
            raise KeyError(project_id)
        return project
