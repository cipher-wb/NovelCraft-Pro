from __future__ import annotations

from typing import Any

from backend.app.core.paths import AppPaths
from backend.app.domain.models.common import utc_now
from backend.app.domain.models.writing import (
    BookAssembledDocument,
    ChapterAssembledDocument,
    ProjectHealthActionableItem,
    ProjectHealthArtifactSummary,
    ProjectHealthBibleStatus,
    ProjectHealthBookArtifact,
    ProjectHealthMemoryStatus,
    ProjectHealthPlannerCounts,
    ProjectHealthReport,
    ProjectHealthScenePipeline,
    SceneDraft,
    VolumeAssembledDocument,
)
from backend.app.repositories.file_repository import FileRepository
from backend.app.repositories.sqlite_repository import SQLiteRepository
from backend.app.services.bible_service import BibleService
from backend.app.services.planner_service import PlannerService
from backend.app.services.project_artifact_inspector import ProjectArtifactInspector


class ProjectHealthService:
    CODE_MISSING_ACCEPTED_SCENE = "missing_accepted_scene"
    CODE_DUPLICATE_ACCEPTED_SCENE = "duplicate_accepted_scene"
    CODE_SCENE_CHECK_BLOCKED = "scene_check_blocked"
    CODE_CHAPTER_ARTIFACT_MISSING = "chapter_artifact_missing"
    CODE_CHAPTER_ARTIFACT_STALE = "chapter_artifact_stale"
    CODE_CHAPTER_CHECK_BLOCKED = "chapter_check_blocked"
    CODE_VOLUME_ARTIFACT_MISSING = "volume_artifact_missing"
    CODE_VOLUME_ARTIFACT_STALE = "volume_artifact_stale"
    CODE_VOLUME_CHECK_BLOCKED = "volume_check_blocked"
    CODE_BOOK_ARTIFACT_MISSING = "book_artifact_missing"
    CODE_BOOK_ARTIFACT_STALE = "book_artifact_stale"
    CODE_BOOK_CHECK_BLOCKED = "book_check_blocked"
    CODE_BOOK_CONTINUITY_BLOCKED = "book_continuity_blocked"
    CODE_MEMORY_DOCUMENT_MISSING = "memory_document_missing"

    def __init__(
        self,
        paths: AppPaths,
        file_repository: FileRepository,
        sqlite_repository: SQLiteRepository,
        bible_service: BibleService,
        planner_service: PlannerService,
    ) -> None:
        self.paths = paths
        self.file_repository = file_repository
        self.sqlite_repository = sqlite_repository
        self.bible_service = bible_service
        self.planner_service = planner_service
        self.inspector = ProjectArtifactInspector(paths, file_repository, planner_service)

    def build_report(self, project_id: str) -> ProjectHealthReport:
        project = self._require_project(project_id)
        slug = project["slug"]
        aggregate = self.bible_service.get_bible_aggregate(project_id)
        volumes = self.planner_service.list_volumes(project_id)
        chapters = [chapter for volume in volumes for chapter in self.planner_service.list_chapters(project_id, volume.volume_id)]
        scenes = [scene for chapter in chapters for scene in self.planner_service.list_scenes(project_id, chapter.chapter_id)]

        actionable_items: list[ProjectHealthActionableItem] = []
        bible = ProjectHealthBibleStatus(
            story_bible_status=aggregate.story_bible.status,
            characters_status=aggregate.characters.status,
            world_status=aggregate.world.status,
            power_system_status=aggregate.power_system.status,
        )
        planner_counts = ProjectHealthPlannerCounts(
            volumes_ready=sum(1 for volume in volumes if volume.status == "ready"),
            chapters_ready=sum(1 for chapter in chapters if chapter.status == "ready"),
            scenes_ready=sum(1 for scene in scenes if scene.status == "ready"),
            volumes_stale=sum(1 for volume in volumes if volume.status == "stale"),
            chapters_stale=sum(1 for chapter in chapters if chapter.status == "stale"),
            scenes_stale=sum(1 for scene in scenes if scene.status == "stale"),
        )

        scene_pipeline = self._build_scene_pipeline(slug, scenes, actionable_items)
        chapter_artifacts = self._build_chapter_artifacts(project_id, slug, chapters, actionable_items)
        volume_artifacts = self._build_volume_artifacts(project_id, slug, volumes, actionable_items)
        book_artifact = self._build_book_artifact(project_id, slug, actionable_items)
        memory = self._build_memory_status(slug, actionable_items)

        overall_status = "clean"
        if any(item.severity == "blocker" for item in actionable_items):
            overall_status = "blocked"
        elif actionable_items:
            overall_status = "warning"

        return ProjectHealthReport(
            project_id=project_id,
            generated_at=utc_now(),
            overall_status=overall_status,
            bible=bible,
            planner_counts=planner_counts,
            scene_pipeline=scene_pipeline,
            chapter_artifacts=chapter_artifacts,
            volume_artifacts=volume_artifacts,
            book_artifact=book_artifact,
            memory=memory,
            actionable_items=actionable_items,
        )

    def _build_scene_pipeline(
        self,
        slug: str,
        scenes: list[Any],
        actionable_items: list[ProjectHealthActionableItem],
    ) -> ProjectHealthScenePipeline:
        accepted_scene_count = 0
        missing_count = 0
        duplicate_count = 0
        blocked_count = 0
        for scene in scenes:
            accepted = self.inspector.accepted_drafts_for_scene(slug, scene.scene_id)
            if len(accepted) == 1:
                accepted_scene_count += 1
                draft = accepted[0]
                if draft.last_check_status in {"blocked", "error"}:
                    blocked_count += 1
                    actionable_items.append(
                        ProjectHealthActionableItem(
                            severity="blocker",
                            code=self.CODE_SCENE_CHECK_BLOCKED,
                            scope="scene",
                            target_id=scene.scene_id,
                            summary="Accepted scene draft is blocked by latest checks.",
                        )
                    )
            elif len(accepted) == 0:
                missing_count += 1
                actionable_items.append(
                    ProjectHealthActionableItem(
                        severity="warning",
                        code=self.CODE_MISSING_ACCEPTED_SCENE,
                        scope="scene",
                        target_id=scene.scene_id,
                        summary="Scene has no unique active accepted draft.",
                    )
                )
            else:
                duplicate_count += 1
                actionable_items.append(
                    ProjectHealthActionableItem(
                        severity="blocker",
                        code=self.CODE_DUPLICATE_ACCEPTED_SCENE,
                        scope="scene",
                        target_id=scene.scene_id,
                        summary="Scene contains multiple active accepted drafts.",
                    )
                )
        return ProjectHealthScenePipeline(
            planned_scene_count=len(scenes),
            accepted_scene_count=accepted_scene_count,
            missing_accepted_scene_count=missing_count,
            duplicate_accepted_scene_count=duplicate_count,
            blocked_scene_check_count=blocked_count,
        )

    def _build_chapter_artifacts(
        self,
        project_id: str,
        slug: str,
        chapters: list[Any],
        actionable_items: list[ProjectHealthActionableItem],
    ) -> ProjectHealthArtifactSummary:
        summary = ProjectHealthArtifactSummary()
        for chapter in chapters:
            path = self.paths.chapter_assembled_path(slug, chapter.chapter_id)
            if not self.file_repository.exists(path):
                summary.missing_count += 1
                actionable_items.append(
                    ProjectHealthActionableItem(
                        severity="warning",
                        code=self.CODE_CHAPTER_ARTIFACT_MISSING,
                        scope="chapter",
                        target_id=chapter.chapter_id,
                        summary="Chapter assembled artifact is missing.",
                    )
                )
                continue
            try:
                artifact = ChapterAssembledDocument.model_validate(self.file_repository.read_json(path))
            except Exception:
                summary.stale_count += 1
                actionable_items.append(
                    ProjectHealthActionableItem(
                        severity="blocker",
                        code=self.CODE_CHAPTER_ARTIFACT_STALE,
                        scope="chapter",
                        target_id=chapter.chapter_id,
                        summary="Chapter artifact is unreadable.",
                    )
                )
                continue

            effective_status = artifact.status
            if artifact.status != "stale" and self.inspector.is_chapter_artifact_stale(project_id, slug, artifact):
                effective_status = "stale"
            if effective_status == "finalized":
                summary.finalized_count += 1
            elif effective_status == "assembled":
                summary.assembled_count += 1
            else:
                summary.stale_count += 1
                actionable_items.append(
                    ProjectHealthActionableItem(
                        severity="warning",
                        code=self.CODE_CHAPTER_ARTIFACT_STALE,
                        scope="chapter",
                        target_id=chapter.chapter_id,
                        summary="Chapter artifact snapshot is stale or marked stale.",
                    )
                )
            if artifact.last_check_status in {"blocked", "error"}:
                summary.blocked_count += 1
                actionable_items.append(
                    ProjectHealthActionableItem(
                        severity="blocker",
                        code=self.CODE_CHAPTER_CHECK_BLOCKED,
                        scope="chapter",
                        target_id=chapter.chapter_id,
                        summary="Chapter latest checks are blocked.",
                    )
                )
        return summary

    def _build_volume_artifacts(
        self,
        project_id: str,
        slug: str,
        volumes: list[Any],
        actionable_items: list[ProjectHealthActionableItem],
    ) -> ProjectHealthArtifactSummary:
        summary = ProjectHealthArtifactSummary()
        for volume in volumes:
            path = self.paths.volume_assembled_path(slug, volume.volume_id)
            if not self.file_repository.exists(path):
                summary.missing_count += 1
                actionable_items.append(
                    ProjectHealthActionableItem(
                        severity="warning",
                        code=self.CODE_VOLUME_ARTIFACT_MISSING,
                        scope="volume",
                        target_id=volume.volume_id,
                        summary="Volume assembled artifact is missing.",
                    )
                )
                continue
            try:
                artifact = VolumeAssembledDocument.model_validate(self.file_repository.read_json(path))
            except Exception:
                summary.stale_count += 1
                actionable_items.append(
                    ProjectHealthActionableItem(
                        severity="blocker",
                        code=self.CODE_VOLUME_ARTIFACT_STALE,
                        scope="volume",
                        target_id=volume.volume_id,
                        summary="Volume artifact is unreadable.",
                    )
                )
                continue

            effective_status = artifact.status
            if artifact.status != "stale" and self.inspector.is_volume_artifact_stale(project_id, slug, artifact):
                effective_status = "stale"
            if effective_status == "finalized":
                summary.finalized_count += 1
            elif effective_status == "assembled":
                summary.assembled_count += 1
            else:
                summary.stale_count += 1
                actionable_items.append(
                    ProjectHealthActionableItem(
                        severity="warning",
                        code=self.CODE_VOLUME_ARTIFACT_STALE,
                        scope="volume",
                        target_id=volume.volume_id,
                        summary="Volume artifact snapshot is stale or marked stale.",
                    )
                )
            if artifact.last_check_status in {"blocked", "error"}:
                summary.blocked_count += 1
                actionable_items.append(
                    ProjectHealthActionableItem(
                        severity="blocker",
                        code=self.CODE_VOLUME_CHECK_BLOCKED,
                        scope="volume",
                        target_id=volume.volume_id,
                        summary="Volume latest checks are blocked.",
                    )
                )
        return summary

    def _build_book_artifact(
        self,
        project_id: str,
        slug: str,
        actionable_items: list[ProjectHealthActionableItem],
    ) -> ProjectHealthBookArtifact:
        path = self.paths.book_assembled_path(slug)
        if not self.file_repository.exists(path):
            actionable_items.append(
                ProjectHealthActionableItem(
                    severity="warning",
                    code=self.CODE_BOOK_ARTIFACT_MISSING,
                    scope="book",
                    target_id="book",
                    summary="Book assembled artifact is missing.",
                )
            )
            return ProjectHealthBookArtifact(status="missing", blocked=False)

        artifact = BookAssembledDocument.model_validate(self.file_repository.read_json(path))
        effective_status = artifact.status
        if artifact.status != "stale" and self.inspector.is_book_artifact_stale(project_id, slug, artifact):
            effective_status = "stale"
            actionable_items.append(
                ProjectHealthActionableItem(
                    severity="warning",
                    code=self.CODE_BOOK_ARTIFACT_STALE,
                    scope="book",
                    target_id="book",
                    summary="Book artifact snapshot is stale or marked stale.",
                )
            )
        blocked = False
        if artifact.last_check_status in {"blocked", "error"}:
            blocked = True
            actionable_items.append(
                ProjectHealthActionableItem(
                    severity="blocker",
                    code=self.CODE_BOOK_CHECK_BLOCKED,
                    scope="book",
                    target_id="book",
                    summary="Book latest checks are blocked.",
                )
            )
        if artifact.last_continuity_check_status in {"blocked", "error"}:
            blocked = True
            actionable_items.append(
                ProjectHealthActionableItem(
                    severity="blocker",
                    code=self.CODE_BOOK_CONTINUITY_BLOCKED,
                    scope="book",
                    target_id="book",
                    summary="Book continuity checks are blocked.",
                )
            )
        return ProjectHealthBookArtifact(status=effective_status, blocked=blocked)

    def _build_memory_status(
        self,
        slug: str,
        actionable_items: list[ProjectHealthActionableItem],
    ) -> ProjectHealthMemoryStatus:
        memory = ProjectHealthMemoryStatus(
            accepted_scenes_exists=self.file_repository.exists(self.paths.accepted_scenes_memory_path(slug)),
            chapter_summaries_exists=self.file_repository.exists(self.paths.chapter_summaries_memory_path(slug)),
            character_state_summaries_exists=self.file_repository.exists(self.paths.character_state_summaries_memory_path(slug)),
            volume_summaries_exists=self.file_repository.exists(self.paths.volume_summaries_memory_path(slug)),
            book_summary_exists=self.file_repository.exists(self.paths.book_summary_memory_path(slug)),
        )
        for target_id, exists in [
            ("accepted_scenes.json", memory.accepted_scenes_exists),
            ("chapter_summaries.json", memory.chapter_summaries_exists),
            ("character_state_summaries.json", memory.character_state_summaries_exists),
            ("volume_summaries.json", memory.volume_summaries_exists),
            ("book_summary.json", memory.book_summary_exists),
        ]:
            if exists:
                continue
            actionable_items.append(
                ProjectHealthActionableItem(
                    severity="warning",
                    code=self.CODE_MEMORY_DOCUMENT_MISSING,
                    scope="memory",
                    target_id=target_id,
                    summary="Derived memory document is missing.",
                )
            )
        return memory

    def _require_project(self, project_id: str) -> dict[str, Any]:
        project = self.sqlite_repository.get_project_record(project_id)
        if project is None:
            raise KeyError(project_id)
        return project
