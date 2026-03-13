from __future__ import annotations

from typing import Any

from backend.app.core.paths import AppPaths
from backend.app.domain.models.common import utc_now
from backend.app.domain.models.issues import VolumeCheckReport
from backend.app.domain.models.planning import ChapterPlan, VolumePlan
from backend.app.domain.models.writing import (
    ChapterAssembledDocument,
    VolumeAssembledDocument,
    VolumeAssembledSourceVersions,
    VolumeChapterOrderItem,
    VolumeProgressStats,
)
from backend.app.repositories.file_repository import FileRepository
from backend.app.repositories.sqlite_repository import SQLiteRepository
from backend.app.services.exceptions import ConflictError
from backend.app.services.memory_service import MemoryService
from backend.app.services.planner_service import PlannerService
from backend.app.services.volume_checks_service import VolumeChecksService


class VolumeAssemblyService:
    def __init__(
        self,
        paths: AppPaths,
        file_repository: FileRepository,
        sqlite_repository: SQLiteRepository,
        planner_service: PlannerService,
        chapter_assembly_service,
        memory_service: MemoryService,
        volume_checks_service: VolumeChecksService,
    ) -> None:
        self.paths = paths
        self.file_repository = file_repository
        self.sqlite_repository = sqlite_repository
        self.planner_service = planner_service
        self.chapter_assembly_service = chapter_assembly_service
        self.memory_service = memory_service
        self.volume_checks_service = volume_checks_service

    def assemble(self, project_id: str, volume_id: str) -> VolumeAssembledDocument:
        project = self._require_project(project_id)
        slug = project["slug"]
        volume, planned_chapters = self._load_ready_volume(project_id, volume_id)
        finalized_chapters = self._load_finalized_chapters(slug, planned_chapters)
        if not finalized_chapters:
            raise ConflictError("At least one finalized chapter is required before assembling volume.")

        content_md = "\n\n".join(artifact.content_md.strip() for _, artifact in finalized_chapters)
        existing = self._read_assembled(slug, volume_id)
        next_version = 1 if existing is None else existing.version + 1
        assembled = VolumeAssembledDocument(
            project_id=project_id,
            volume_id=volume.volume_id,
            volume_no=volume.volume_no,
            version=next_version,
            status="assembled",
            updated_at=utc_now(),
            source_versions=VolumeAssembledSourceVersions(
                volume_version=volume.version,
                planned_chapter_versions={chapter.chapter_id: chapter.version for chapter in planned_chapters},
                finalized_chapter_versions={chapter.chapter_id: artifact.version for chapter, artifact in finalized_chapters},
            ),
            planned_chapter_order=[chapter.chapter_id for chapter in planned_chapters],
            chapter_order=[
                VolumeChapterOrderItem(
                    chapter_id=chapter.chapter_id,
                    chapter_no=chapter.chapter_no,
                    assembled_version=artifact.version,
                )
                for chapter, artifact in finalized_chapters
            ],
            content_md=content_md,
            summary=self._build_summary(finalized_chapters),
            hook=self._build_hook(volume, planned_chapters, finalized_chapters),
            progress_stats=self._build_progress_stats(planned_chapters, finalized_chapters),
            latest_check_report_path=self.paths.relative_to_project(slug, self.paths.volume_check_latest_path(slug, volume.volume_id)),
            last_check_status=None,
            last_check_blocker_count=0,
            last_check_warning_count=0,
            finalized_at=None,
            finalized_from_assembly_version=None,
        )
        self._write_assembled(slug, assembled)
        self.volume_checks_service.run_for_volume(project_id, assembled, trigger="assemble_auto")
        return self.get_assembled(project_id, volume_id)

    def get_assembled(self, project_id: str, volume_id: str) -> VolumeAssembledDocument:
        project = self._require_project(project_id)
        slug = project["slug"]
        assembled = self._read_assembled(slug, volume_id)
        if assembled is None:
            raise KeyError(volume_id)
        return self._refresh_stale_status(project_id, slug, assembled)

    def recheck(self, project_id: str, volume_id: str) -> VolumeCheckReport:
        assembled = self.get_assembled(project_id, volume_id)
        return self.volume_checks_service.run_for_volume(project_id, assembled, trigger="manual_recheck")

    def get_latest_report(self, project_id: str, volume_id: str) -> VolumeCheckReport | None:
        return self.volume_checks_service.get_latest_report(project_id, volume_id)

    def finalize(self, project_id: str, volume_id: str) -> VolumeAssembledDocument:
        project = self._require_project(project_id)
        slug = project["slug"]
        assembled = self.get_assembled(project_id, volume_id)
        if assembled.status == "stale":
            raise ConflictError("Stale volume must be re-assembled before finalize.")
        if assembled.status == "finalized":
            return assembled

        report = self.volume_checks_service.ensure_finalize_allowed(project_id, assembled)
        assembled = self.get_assembled(project_id, volume_id)
        if report.overall_status in {"blocked", "error"}:
            raise ConflictError("Volume finalize blocked by latest volume checks.")
        if assembled.status == "stale":
            raise ConflictError("Stale volume must be re-assembled before finalize.")

        volume_plan = self.planner_service.get_volume(project_id, volume_id)
        assembled.status = "finalized"
        assembled.finalized_at = utc_now()
        assembled.finalized_from_assembly_version = assembled.version
        self._write_assembled(slug, assembled)
        self.memory_service.update_finalized_volume_summary(slug, assembled, volume_plan)
        return self.get_assembled(project_id, volume_id)

    def _load_ready_volume(self, project_id: str, volume_id: str) -> tuple[VolumePlan, list[ChapterPlan]]:
        volume = self.planner_service.get_volume(project_id, volume_id)
        if volume.status != "ready":
            raise ConflictError("Volume must be ready before assembling volume.")
        planned_chapters = sorted(self.planner_service.list_chapters(project_id, volume_id), key=lambda item: item.chapter_no)
        return volume, planned_chapters

    def _load_finalized_chapters(self, slug: str, planned_chapters: list[ChapterPlan]) -> list[tuple[ChapterPlan, ChapterAssembledDocument]]:
        finalized: list[tuple[ChapterPlan, ChapterAssembledDocument]] = []
        for chapter in planned_chapters:
            path = self.paths.chapter_assembled_path(slug, chapter.chapter_id)
            if not self.file_repository.exists(path):
                continue
            try:
                artifact = ChapterAssembledDocument.model_validate(self.file_repository.read_json(path))
            except Exception as error:
                raise ConflictError(f"Chapter artifact for {chapter.chapter_id} is invalid.") from error
            if artifact.status != "finalized":
                continue
            if artifact.version <= 0:
                raise ConflictError(f"Finalized chapter artifact for {chapter.chapter_id} has invalid assembled version.")
            finalized.append((chapter, artifact))
        return finalized

    def _build_summary(self, finalized_chapters: list[tuple[ChapterPlan, ChapterAssembledDocument]]) -> str:
        parts: list[str] = []
        for chapter, artifact in finalized_chapters[:4]:
            piece = artifact.summary.strip() or artifact.hook.strip() or self._non_whitespace_prefix(artifact.content_md, 120)
            if piece:
                parts.append(f"第{chapter.chapter_no}章：{piece}")
        return " ".join(parts).strip()

    def _build_hook(
        self,
        volume: VolumePlan,
        planned_chapters: list[ChapterPlan],
        finalized_chapters: list[tuple[ChapterPlan, ChapterAssembledDocument]],
    ) -> str:
        if len(finalized_chapters) == len(planned_chapters) and volume.closing_hook.strip():
            return volume.closing_hook.strip()
        _, last_artifact = finalized_chapters[-1]
        return last_artifact.hook.strip() or last_artifact.summary.strip()

    def _build_progress_stats(
        self,
        planned_chapters: list[ChapterPlan],
        finalized_chapters: list[tuple[ChapterPlan, ChapterAssembledDocument]],
    ) -> VolumeProgressStats:
        planned_count = len(planned_chapters)
        finalized_count = len(finalized_chapters)
        chapter_nos = [chapter.chapter_no for chapter, _ in finalized_chapters]
        return VolumeProgressStats(
            planned_chapter_count=planned_count,
            finalized_chapter_count=finalized_count,
            completion_ratio=(finalized_count / planned_count) if planned_count else 0.0,
            scene_count_total=sum(artifact.basic_stats.scene_count for _, artifact in finalized_chapters),
            paragraph_count_total=sum(artifact.basic_stats.paragraph_count for _, artifact in finalized_chapters),
            char_count_total=sum(artifact.basic_stats.char_count for _, artifact in finalized_chapters),
            first_finalized_chapter_no=min(chapter_nos) if chapter_nos else None,
            last_finalized_chapter_no=max(chapter_nos) if chapter_nos else None,
        )

    def _refresh_stale_status(self, project_id: str, slug: str, assembled: VolumeAssembledDocument) -> VolumeAssembledDocument:
        volume, planned_chapters = self._load_ready_volume(project_id, assembled.volume_id)
        finalized_chapters = self._load_finalized_chapters(slug, planned_chapters)
        stale = False
        if volume.version != assembled.source_versions.volume_version:
            stale = True
        planned_order = [chapter.chapter_id for chapter in planned_chapters]
        if planned_order != assembled.planned_chapter_order:
            stale = True
        planned_versions = {chapter.chapter_id: chapter.version for chapter in planned_chapters}
        if planned_versions != assembled.source_versions.planned_chapter_versions:
            stale = True
        finalized_versions = {chapter.chapter_id: artifact.version for chapter, artifact in finalized_chapters}
        if finalized_versions != assembled.source_versions.finalized_chapter_versions:
            stale = True
        current_order = [(chapter.chapter_id, chapter.chapter_no, artifact.version) for chapter, artifact in finalized_chapters]
        stored_order = [(item.chapter_id, item.chapter_no, item.assembled_version) for item in assembled.chapter_order]
        if current_order != stored_order:
            stale = True
        if stale and assembled.status != "stale":
            assembled.status = "stale"
            assembled.updated_at = utc_now()
            self._write_assembled(slug, assembled)
        return assembled

    def _non_whitespace_prefix(self, content_md: str, limit: int) -> str:
        return "".join(content_md.split())[:limit]

    def _read_assembled(self, slug: str, volume_id: str) -> VolumeAssembledDocument | None:
        path = self.paths.volume_assembled_path(slug, volume_id)
        if not self.file_repository.exists(path):
            return None
        return VolumeAssembledDocument.model_validate(self.file_repository.read_json(path))

    def _write_assembled(self, slug: str, assembled: VolumeAssembledDocument) -> None:
        self.file_repository.write_json(self.paths.volume_assembled_path(slug, assembled.volume_id), assembled.model_dump(mode="json"))

    def _require_project(self, project_id: str) -> dict[str, Any]:
        project = self.sqlite_repository.get_project_record(project_id)
        if project is None:
            raise KeyError(project_id)
        return project
