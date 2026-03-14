from __future__ import annotations

from backend.app.core.paths import AppPaths
from backend.app.domain.models.planning import ChapterPlan, ScenePlan, VolumePlan
from backend.app.domain.models.writing import (
    BookAssembledDocument,
    ChapterAssembledDocument,
    SceneDraft,
    VolumeAssembledDocument,
)
from backend.app.repositories.file_repository import FileRepository
from backend.app.services.planner_service import PlannerService


class ProjectArtifactInspector:
    def __init__(
        self,
        paths: AppPaths,
        file_repository: FileRepository,
        planner_service: PlannerService,
    ) -> None:
        self.paths = paths
        self.file_repository = file_repository
        self.planner_service = planner_service

    def accepted_drafts_for_scene(self, slug: str, scene_id: str) -> list[SceneDraft]:
        scene_dir = self.paths.scene_drafts_dir(slug, scene_id)
        if not scene_dir.exists():
            return []
        accepted: list[SceneDraft] = []
        for draft_path in sorted(scene_dir.glob("draft-*.json")):
            draft = SceneDraft.model_validate(self.file_repository.read_json(draft_path))
            if draft.status == "accepted":
                accepted.append(draft)
        return accepted

    def current_unique_accepted_draft_ids(self, slug: str, scenes: list[ScenePlan]) -> dict[str, str]:
        accepted_by_scene: dict[str, str] = {}
        for scene in scenes:
            accepted = self.accepted_drafts_for_scene(slug, scene.scene_id)
            if len(accepted) == 1:
                accepted_by_scene[scene.scene_id] = accepted[0].draft_id
        return accepted_by_scene

    def load_finalized_chapter_artifacts(
        self,
        slug: str,
        planned_chapters: list[ChapterPlan],
    ) -> list[tuple[ChapterPlan, ChapterAssembledDocument]]:
        finalized: list[tuple[ChapterPlan, ChapterAssembledDocument]] = []
        for chapter in planned_chapters:
            path = self.paths.chapter_assembled_path(slug, chapter.chapter_id)
            if not self.file_repository.exists(path):
                continue
            artifact = ChapterAssembledDocument.model_validate(self.file_repository.read_json(path))
            if artifact.status == "finalized" and artifact.version > 0:
                finalized.append((chapter, artifact))
        return finalized

    def load_finalized_volume_artifacts(
        self,
        slug: str,
        planned_volumes: list[VolumePlan],
    ) -> list[tuple[VolumePlan, VolumeAssembledDocument]]:
        finalized: list[tuple[VolumePlan, VolumeAssembledDocument]] = []
        for volume in planned_volumes:
            path = self.paths.volume_assembled_path(slug, volume.volume_id)
            if not self.file_repository.exists(path):
                continue
            artifact = VolumeAssembledDocument.model_validate(self.file_repository.read_json(path))
            if artifact.status == "finalized" and artifact.version > 0:
                finalized.append((volume, artifact))
        return finalized

    def is_chapter_artifact_stale(self, project_id: str, slug: str, assembled: ChapterAssembledDocument) -> bool:
        volume = self.planner_service.get_volume(project_id, assembled.volume_id)
        chapter = self.planner_service.get_chapter(project_id, assembled.chapter_id)
        scenes = sorted(self.planner_service.list_scenes(project_id, assembled.chapter_id), key=lambda item: item.scene_no)
        if volume.version != assembled.source_versions.volume_version:
            return True
        if chapter.version != assembled.source_versions.chapter_version:
            return True
        current_scene_versions = {scene.scene_id: scene.version for scene in scenes}
        if current_scene_versions != assembled.source_versions.scene_versions:
            return True
        current_order = [(scene.scene_id, scene.scene_no) for scene in scenes]
        stored_order = [(item.scene_id, item.scene_no) for item in assembled.scene_order]
        if current_order != stored_order:
            return True
        current_accepted_ids = self.current_unique_accepted_draft_ids(slug, scenes)
        if current_accepted_ids != assembled.source_versions.accepted_draft_ids:
            return True
        return False

    def is_volume_artifact_stale(self, project_id: str, slug: str, assembled: VolumeAssembledDocument) -> bool:
        volume = self.planner_service.get_volume(project_id, assembled.volume_id)
        planned_chapters = sorted(self.planner_service.list_chapters(project_id, assembled.volume_id), key=lambda item: item.chapter_no)
        if volume.status != "ready":
            return True
        if volume.version != assembled.source_versions.volume_version:
            return True
        planned_order = [chapter.chapter_id for chapter in planned_chapters]
        if planned_order != assembled.planned_chapter_order:
            return True
        planned_versions = {chapter.chapter_id: chapter.version for chapter in planned_chapters}
        if planned_versions != assembled.source_versions.planned_chapter_versions:
            return True
        finalized_versions = {
            chapter.chapter_id: artifact.version
            for chapter, artifact in self.load_finalized_chapter_artifacts(slug, planned_chapters)
        }
        if finalized_versions != assembled.source_versions.finalized_chapter_versions:
            return True
        current_order = [
            (chapter.chapter_id, chapter.chapter_no, artifact.version)
            for chapter, artifact in self.load_finalized_chapter_artifacts(slug, planned_chapters)
        ]
        stored_order = [(item.chapter_id, item.chapter_no, item.assembled_version) for item in assembled.chapter_order]
        if current_order != stored_order:
            return True
        return False

    def is_book_artifact_stale(self, project_id: str, slug: str, assembled: BookAssembledDocument) -> bool:
        outline = self.planner_service.get_master_outline(project_id)
        planned_volumes = sorted(self.planner_service.list_volumes(project_id), key=lambda item: item.volume_no)
        if outline.version != assembled.source_versions.master_outline_version:
            return True
        planned_order = [volume.volume_id for volume in planned_volumes]
        if planned_order != assembled.planned_volume_order:
            return True
        planned_versions = {volume.volume_id: volume.version for volume in planned_volumes}
        if planned_versions != assembled.source_versions.planned_volume_versions:
            return True
        finalized_versions = {
            volume.volume_id: artifact.version
            for volume, artifact in self.load_finalized_volume_artifacts(slug, planned_volumes)
        }
        if finalized_versions != assembled.source_versions.finalized_volume_versions:
            return True
        current_order = [
            (volume.volume_id, volume.volume_no, artifact.version)
            for volume, artifact in self.load_finalized_volume_artifacts(slug, planned_volumes)
        ]
        stored_order = [(item.volume_id, item.volume_no, item.assembled_version) for item in assembled.volume_order]
        if current_order != stored_order:
            return True
        return False
