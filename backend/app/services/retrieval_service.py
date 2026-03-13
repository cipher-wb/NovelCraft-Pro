from __future__ import annotations

from backend.app.core.paths import AppPaths
from backend.app.domain.models.planning import ChapterPlan
from backend.app.domain.models.writing import (
    AcceptedSceneMemoryDocument,
    ChapterSummariesMemoryDocument,
    CharacterStateSummariesMemoryDocument,
    RetrievedCharacterStateBrief,
    RetrievedMemoryContext,
    RetrievedPreviousChapterSummary,
    RetrievedSceneSummary,
    RetrievedVolumeSummary,
    VolumeSummariesMemoryDocument,
)
from backend.app.repositories.file_repository import FileRepository
from backend.app.repositories.sqlite_repository import SQLiteRepository
from backend.app.services.planner_service import PlannerService


class RetrievalService:
    WARNING_VOLUME_SUMMARIES_UNAVAILABLE = "volume_summaries_unavailable"
    WARNING_VOLUME_SUMMARY_DUPLICATE_DETECTED = "volume_summary_duplicate_detected"

    def __init__(
        self,
        paths: AppPaths,
        file_repository: FileRepository,
        sqlite_repository: SQLiteRepository,
        planner_service: PlannerService,
    ) -> None:
        self.paths = paths
        self.file_repository = file_repository
        self.sqlite_repository = sqlite_repository
        self.planner_service = planner_service

    def retrieve_for_scene(self, project_id: str, scene_id: str) -> RetrievedMemoryContext:
        warnings: list[str] = []
        project = self._require_project(project_id)
        slug = project["slug"]
        scene = self.planner_service.get_scene(project_id, scene_id)
        chapter = self.planner_service.get_chapter(project_id, scene.chapter_id)
        volume = self.planner_service.get_volume(project_id, scene.volume_id)

        accepted_document = self._safe_read_document(
            self.paths.accepted_scenes_memory_path(slug),
            AcceptedSceneMemoryDocument,
            project_id,
            warnings,
            "accepted_scenes_unavailable",
        )
        chapter_document = self._safe_read_document(
            self.paths.chapter_summaries_memory_path(slug),
            ChapterSummariesMemoryDocument,
            project_id,
            warnings,
            "chapter_summaries_unavailable",
        )
        character_document = self._safe_read_document(
            self.paths.character_state_summaries_memory_path(slug),
            CharacterStateSummariesMemoryDocument,
            project_id,
            warnings,
            "character_state_summaries_unavailable",
        )
        volume_document = self._safe_read_document(
            self.paths.volume_summaries_memory_path(slug),
            VolumeSummariesMemoryDocument,
            project_id,
            warnings,
            self.WARNING_VOLUME_SUMMARIES_UNAVAILABLE,
        )

        recent_scene_summaries = self._recent_scene_summaries(accepted_document, chapter.chapter_id, scene.scene_no)
        previous_chapter_summary = self._previous_chapter_summary(chapter_document, chapter, volume)
        previous_volume_summary = self._previous_volume_summary(
            project_id,
            volume_document,
            chapter,
            volume.volume_no,
            warnings,
        )
        character_state_briefs = self._character_state_briefs(character_document, scene.character_ids)

        return RetrievedMemoryContext(
            strategy="deterministic_v1",
            warnings=warnings,
            recent_scene_summaries=recent_scene_summaries,
            previous_chapter_summary=previous_chapter_summary,
            previous_volume_summary=previous_volume_summary,
            character_state_briefs=character_state_briefs,
        )

    def _safe_read_document(self, path, model_cls, project_id: str, warnings: list[str], warning_code: str):
        if not self.file_repository.exists(path):
            warnings.append(warning_code)
            return model_cls(project_id=project_id, updated_at="2026-03-12T00:00:00Z")
        try:
            return model_cls.model_validate(self.file_repository.read_json(path))
        except Exception:
            warnings.append(warning_code)
            return model_cls(project_id=project_id, updated_at="2026-03-12T00:00:00Z")

    def _recent_scene_summaries(
        self,
        document: AcceptedSceneMemoryDocument,
        chapter_id: str,
        target_scene_no: int,
    ) -> list[RetrievedSceneSummary]:
        candidates = sorted(
            [item for item in document.items if item.chapter_id == chapter_id and item.scene_no < target_scene_no],
            key=lambda value: (value.scene_no, value.draft_id),
            reverse=True,
        )
        seen: set[str] = set()
        results: list[RetrievedSceneSummary] = []
        for item in candidates:
            if item.scene_id in seen:
                continue
            seen.add(item.scene_id)
            results.append(
                RetrievedSceneSummary(
                    scene_id=item.scene_id,
                    chapter_id=item.chapter_id,
                    scene_no=item.scene_no,
                    scene_title=item.scene_title,
                    summary=item.summary,
                    scene_goal=item.scene_goal,
                    scene_outcome=item.scene_outcome,
                )
            )
            if len(results) >= 3:
                break
        return results

    def _previous_chapter_summary(
        self,
        document: ChapterSummariesMemoryDocument,
        chapter: ChapterPlan,
        volume,
    ) -> RetrievedPreviousChapterSummary | None:
        same_volume = [item for item in document.items if item.volume_id == volume.volume_id and item.chapter_no < chapter.chapter_no]
        candidates = same_volume or [item for item in document.items if item.chapter_no < chapter.chapter_no]
        if not candidates:
            return None
        previous = sorted(candidates, key=lambda value: (value.chapter_no, value.chapter_id))[-1]
        return RetrievedPreviousChapterSummary(
            chapter_id=previous.chapter_id,
            chapter_no=previous.chapter_no,
            chapter_title=previous.chapter_title,
            summary=previous.summary,
            key_turns=previous.key_turns,
        )

    def _character_state_briefs(
        self,
        document: CharacterStateSummariesMemoryDocument,
        character_ids: list[str],
    ) -> list[RetrievedCharacterStateBrief]:
        ordered = sorted(
            document.items,
            key=lambda value: (value.last_chapter_no, value.last_scene_no, value.updated_at.isoformat(), value.source_draft_id),
        )
        latest_by_character: dict[str, RetrievedCharacterStateBrief] = {}
        for item in ordered:
            latest_by_character[item.character_id] = RetrievedCharacterStateBrief(
                character_id=item.character_id,
                character_name=item.character_name,
                last_scene_id=item.last_scene_id,
                last_chapter_no=item.last_chapter_no,
                last_scene_no=item.last_scene_no,
                latest_location_id=item.latest_location_id,
                latest_scene_summary=item.latest_scene_summary,
                last_scene_goal=item.last_scene_goal,
                last_scene_outcome=item.last_scene_outcome,
                related_character_ids=item.related_character_ids,
            )

        results: list[RetrievedCharacterStateBrief] = []
        seen: set[str] = set()
        for character_id in character_ids:
            if character_id in seen:
                continue
            seen.add(character_id)
            brief = latest_by_character.get(character_id)
            if brief is not None:
                results.append(brief)
        return results

    def _previous_volume_summary(
        self,
        project_id: str,
        document: VolumeSummariesMemoryDocument,
        chapter: ChapterPlan,
        current_volume_no: int,
        warnings: list[str],
    ) -> RetrievedVolumeSummary | None:
        planned_chapters = sorted(
            self.planner_service.list_chapters(project_id, chapter.volume_id),
            key=lambda value: value.chapter_no,
        )
        chapter_ids_in_order = [item.chapter_id for item in planned_chapters]
        if chapter.chapter_id not in chapter_ids_in_order:
            return None
        chapter_index = chapter_ids_in_order.index(chapter.chapter_id)
        if chapter_index not in {0, 1}:
            return None

        candidates = [item for item in document.items if item.volume_no < current_volume_no]
        if not candidates:
            return None

        target_volume_no = max(item.volume_no for item in candidates)
        matching = [item for item in candidates if item.volume_no == target_volume_no]
        if len(matching) > 1:
            warnings.append(self.WARNING_VOLUME_SUMMARY_DUPLICATE_DETECTED)
        chosen = sorted(matching, key=lambda value: (value.volume_no, value.updated_at, value.volume_id))[-1]
        return RetrievedVolumeSummary(
            volume_id=chosen.volume_id,
            volume_no=chosen.volume_no,
            title=chosen.title,
            summary=chosen.summary,
            hook=chosen.hook,
            planned_chapter_count=chosen.planned_chapter_count,
            finalized_chapter_count=chosen.finalized_chapter_count,
            selection_reason="volume_boundary" if chapter_index == 0 else "early_volume_context",
        )

    def _require_project(self, project_id: str) -> dict[str, str]:
        project = self.sqlite_repository.get_project_record(project_id)
        if project is None:
            raise KeyError(project_id)
        return project
