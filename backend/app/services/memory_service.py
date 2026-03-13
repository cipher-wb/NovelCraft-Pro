from __future__ import annotations

from typing import Any

from backend.app.core.paths import AppPaths
from backend.app.domain.models.common import utc_now
from backend.app.domain.models.planning import ChapterPlan, ScenePlan, VolumePlan
from backend.app.domain.models.writing import (
    AcceptedSceneMemoryDocument,
    AcceptedSceneMemoryItem,
    BookAssembledDocument,
    BookSummaryMemoryDocument,
    ChapterAssembledDocument,
    ChapterSummariesMemoryDocument,
    ChapterSummaryMemoryItem,
    CharacterStateSummariesMemoryDocument,
    CharacterStateSummaryMemoryItem,
    MemoryIngestResult,
    SceneDraft,
    VolumeAssembledDocument,
    VolumeSummariesMemoryDocument,
    VolumeSummaryMemoryItem,
)
from backend.app.repositories.file_repository import FileRepository
from backend.app.services.bible_service import BibleService


class MemoryService:
    def __init__(self, paths: AppPaths, file_repository: FileRepository, bible_service: BibleService) -> None:
        self.paths = paths
        self.file_repository = file_repository
        self.bible_service = bible_service

    def ingest_accepted_draft(
        self,
        slug: str,
        draft: SceneDraft,
        scene: ScenePlan,
        chapter: ChapterPlan,
        volume: VolumePlan,
    ) -> MemoryIngestResult:
        accepted_doc = self.read_accepted_scenes(slug, draft.project_id)
        accepted_item = self._upsert_accepted_scene(accepted_doc, draft, scene, chapter, volume)
        self._write_accepted_scenes(slug, accepted_doc)

        chapter_doc = self.read_chapter_summaries(slug, draft.project_id)
        chapter_item: ChapterSummaryMemoryItem | None = None
        chapter_assembled = self._read_chapter_assembled(slug, chapter.chapter_id)
        if chapter_assembled is None or chapter_assembled.status != "finalized":
            chapter_item = self._recompute_chapter_summary(chapter_doc, accepted_doc, chapter)
            self._write_chapter_summaries(slug, chapter_doc)

        character_doc = self.read_character_state_summaries(slug, draft.project_id)
        aggregate = self.bible_service.get_bible_aggregate(draft.project_id)
        self._recompute_character_states(character_doc, accepted_doc, aggregate.characters.items)
        self._write_character_state_summaries(slug, character_doc)

        return MemoryIngestResult(
            accepted_scene_item=accepted_item,
            chapter_summary_item=chapter_item,
            character_state_count=len(character_doc.items),
        )

    def update_finalized_chapter_summary(self, slug: str, assembled: ChapterAssembledDocument) -> ChapterSummaryMemoryItem:
        document = self.read_chapter_summaries(slug, assembled.project_id)
        document.items = [item for item in document.items if item.chapter_id != assembled.chapter_id]
        last_scene = assembled.scene_order[-1] if assembled.scene_order else None
        chapter_item = ChapterSummaryMemoryItem(
            chapter_id=assembled.chapter_id,
            volume_id=assembled.volume_id,
            chapter_no=assembled.chapter_no,
            chapter_title="",
            accepted_scene_ids=[item.scene_id for item in assembled.scene_order],
            accepted_scene_count=len(assembled.scene_order),
            summary=assembled.summary,
            hook=assembled.hook,
            summary_source="finalized_chapter",
            key_turns=[assembled.hook] if assembled.hook else [],
            last_scene_id=last_scene.scene_id if last_scene else None,
            last_scene_no=last_scene.scene_no if last_scene else None,
            updated_from_draft_id=last_scene.accepted_draft_id if last_scene else None,
            updated_at=utc_now(),
        )
        document.items.append(chapter_item)
        document.items = sorted(document.items, key=lambda value: (value.chapter_no, value.chapter_id))
        document.version += 1
        document.updated_at = utc_now()
        self._write_chapter_summaries(slug, document)
        return chapter_item

    def read_accepted_scenes(self, slug: str, project_id: str) -> AcceptedSceneMemoryDocument:
        path = self.paths.accepted_scenes_memory_path(slug)
        if self.file_repository.exists(path):
            return AcceptedSceneMemoryDocument.model_validate(self.file_repository.read_json(path))
        document = AcceptedSceneMemoryDocument(project_id=project_id, updated_at=utc_now())
        self._write_accepted_scenes(slug, document)
        return document

    def read_chapter_summaries(self, slug: str, project_id: str) -> ChapterSummariesMemoryDocument:
        path = self.paths.chapter_summaries_memory_path(slug)
        if self.file_repository.exists(path):
            return ChapterSummariesMemoryDocument.model_validate(self.file_repository.read_json(path))
        document = ChapterSummariesMemoryDocument(project_id=project_id, updated_at=utc_now())
        self._write_chapter_summaries(slug, document)
        return document

    def read_character_state_summaries(self, slug: str, project_id: str) -> CharacterStateSummariesMemoryDocument:
        path = self.paths.character_state_summaries_memory_path(slug)
        if self.file_repository.exists(path):
            return CharacterStateSummariesMemoryDocument.model_validate(self.file_repository.read_json(path))
        document = CharacterStateSummariesMemoryDocument(project_id=project_id, updated_at=utc_now())
        self._write_character_state_summaries(slug, document)
        return document

    def read_volume_summaries(self, slug: str, project_id: str) -> VolumeSummariesMemoryDocument:
        path = self.paths.volume_summaries_memory_path(slug)
        if self.file_repository.exists(path):
            return VolumeSummariesMemoryDocument.model_validate(self.file_repository.read_json(path))
        document = VolumeSummariesMemoryDocument(project_id=project_id, updated_at=utc_now())
        self._write_volume_summaries(slug, document)
        return document

    def read_book_summary(self, slug: str, project_id: str) -> BookSummaryMemoryDocument:
        path = self.paths.book_summary_memory_path(slug)
        if self.file_repository.exists(path):
            return BookSummaryMemoryDocument.model_validate(self.file_repository.read_json(path))
        document = BookSummaryMemoryDocument(project_id=project_id, updated_at=utc_now())
        self._write_book_summary(slug, document)
        return document

    def _upsert_accepted_scene(
        self,
        document: AcceptedSceneMemoryDocument,
        draft: SceneDraft,
        scene: ScenePlan,
        chapter: ChapterPlan,
        volume: VolumePlan,
    ) -> AcceptedSceneMemoryItem:
        summary = draft.summary or self._fallback_summary(draft.content_md, scene.title)
        item = AcceptedSceneMemoryItem(
            memory_id=f"mem_{draft.draft_id}",
            scene_id=scene.scene_id,
            chapter_id=scene.chapter_id,
            volume_id=scene.volume_id,
            draft_id=draft.draft_id,
            chapter_no=draft.chapter_no,
            scene_no=draft.scene_no,
            volume_no=volume.volume_no,
            chapter_title=chapter.title,
            scene_title=scene.title,
            scene_type=scene.scene_type,
            summary=summary,
            summary_source="draft_summary" if draft.summary else "heuristic_fallback",
            scene_goal=scene.goal,
            scene_outcome=scene.outcome,
            character_ids=scene.character_ids,
            faction_ids=chapter.faction_ids,
            location_id=scene.location_id,
            time_anchor=scene.time_anchor,
            accepted_at=draft.accepted_at or utc_now(),
            source_scene_version=draft.source_scene_version,
        )
        document.items = [existing for existing in document.items if existing.scene_id != scene.scene_id]
        document.items.append(item)
        document.items = sorted(document.items, key=lambda value: (value.chapter_no, value.scene_no, value.draft_id))
        document.version += 1
        document.updated_at = utc_now()
        return item

    def _recompute_chapter_summary(
        self,
        document: ChapterSummariesMemoryDocument,
        accepted_document: AcceptedSceneMemoryDocument,
        chapter: ChapterPlan,
    ) -> ChapterSummaryMemoryItem | None:
        chapter_items = sorted(
            [item for item in accepted_document.items if item.chapter_id == chapter.chapter_id],
            key=lambda value: (value.scene_no, value.draft_id),
        )
        document.items = [item for item in document.items if item.chapter_id != chapter.chapter_id]
        if not chapter_items:
            document.version += 1
            document.updated_at = utc_now()
            document.items = sorted(document.items, key=lambda value: (value.chapter_no, value.chapter_id))
            return None

        summary_parts = [f"{item.scene_title}：{item.summary}" for item in chapter_items[:3]]
        key_turns = [f"{item.scene_title}：{item.scene_goal} -> {item.scene_outcome}" for item in chapter_items[:3]]
        chapter_item = ChapterSummaryMemoryItem(
            chapter_id=chapter.chapter_id,
            volume_id=chapter.volume_id,
            chapter_no=chapter.chapter_no,
            chapter_title=chapter.title,
            accepted_scene_ids=[item.scene_id for item in chapter_items],
            accepted_scene_count=len(chapter_items),
            summary=" | ".join(summary_parts),
            summary_source="accepted_scene_rollup",
            key_turns=key_turns,
            last_scene_id=chapter_items[-1].scene_id,
            last_scene_no=chapter_items[-1].scene_no,
            updated_from_draft_id=chapter_items[-1].draft_id,
            updated_at=utc_now(),
        )
        document.items.append(chapter_item)
        document.items = sorted(document.items, key=lambda value: (value.chapter_no, value.chapter_id))
        document.version += 1
        document.updated_at = utc_now()
        return chapter_item

    def _recompute_character_states(
        self,
        document: CharacterStateSummariesMemoryDocument,
        accepted_document: AcceptedSceneMemoryDocument,
        characters: list[Any],
    ) -> None:
        character_names = {item.character_id: item.name for item in characters}
        latest_by_character: dict[str, CharacterStateSummaryMemoryItem] = {}
        ordered_items = sorted(
            accepted_document.items,
            key=lambda value: (value.chapter_no, value.scene_no, value.accepted_at.isoformat(), value.draft_id),
        )
        for item in ordered_items:
            unique_related = []
            seen_related: set[str] = set()
            for related in item.character_ids:
                if related in seen_related:
                    continue
                seen_related.add(related)
                unique_related.append(related)
            for character_id in unique_related:
                related_character_ids = [related for related in unique_related if related != character_id]
                latest_by_character[character_id] = CharacterStateSummaryMemoryItem(
                    character_id=character_id,
                    character_name=character_names.get(character_id, character_id),
                    last_scene_id=item.scene_id,
                    last_chapter_id=item.chapter_id,
                    last_volume_id=item.volume_id,
                    last_chapter_no=item.chapter_no,
                    last_scene_no=item.scene_no,
                    latest_location_id=item.location_id,
                    latest_time_anchor=item.time_anchor,
                    latest_scene_summary=item.summary,
                    last_scene_goal=item.scene_goal,
                    last_scene_outcome=item.scene_outcome,
                    related_character_ids=related_character_ids,
                    source_draft_id=item.draft_id,
                    updated_at=utc_now(),
                )
        document.items = sorted(latest_by_character.values(), key=lambda value: value.character_id)
        document.version += 1
        document.updated_at = utc_now()

    def _write_accepted_scenes(self, slug: str, document: AcceptedSceneMemoryDocument) -> None:
        self.file_repository.write_json(self.paths.accepted_scenes_memory_path(slug), document.model_dump(mode="json"))

    def _write_chapter_summaries(self, slug: str, document: ChapterSummariesMemoryDocument) -> None:
        self.file_repository.write_json(self.paths.chapter_summaries_memory_path(slug), document.model_dump(mode="json"))

    def _write_character_state_summaries(self, slug: str, document: CharacterStateSummariesMemoryDocument) -> None:
        self.file_repository.write_json(self.paths.character_state_summaries_memory_path(slug), document.model_dump(mode="json"))

    def update_finalized_volume_summary(self, slug: str, assembled: VolumeAssembledDocument, volume_plan: VolumePlan) -> VolumeSummaryMemoryItem:
        document = self.read_volume_summaries(slug, assembled.project_id)
        document.items = [item for item in document.items if item.volume_id != assembled.volume_id]
        item = VolumeSummaryMemoryItem(
            volume_id=assembled.volume_id,
            volume_no=assembled.volume_no,
            title=volume_plan.title,
            summary=assembled.summary,
            hook=assembled.hook,
            planned_chapter_count=assembled.progress_stats.planned_chapter_count,
            finalized_chapter_count=assembled.progress_stats.finalized_chapter_count,
            finalized_chapter_ids=[entry.chapter_id for entry in assembled.chapter_order],
            updated_at=utc_now(),
        )
        document.items.append(item)
        document.items = sorted(document.items, key=lambda value: (value.volume_no, value.volume_id))
        document.version += 1
        document.updated_at = utc_now()
        self._write_volume_summaries(slug, document)
        return item

    def update_finalized_book_summary(self, slug: str, assembled: BookAssembledDocument) -> BookSummaryMemoryDocument:
        document = self.read_book_summary(slug, assembled.project_id)
        document.version += 1
        document.updated_at = utc_now()
        document.summary = assembled.summary
        document.hook = assembled.hook
        document.planned_volume_count = assembled.progress_stats.planned_volume_count
        document.finalized_volume_count = assembled.progress_stats.finalized_volume_count
        document.finalized_volume_ids = [item.volume_id for item in assembled.volume_order]
        self._write_book_summary(slug, document)
        return document

    def _fallback_summary(self, content_md: str, title: str) -> str:
        text = " ".join(part.strip() for part in content_md.splitlines() if part.strip())
        if not text:
            return title
        return text[:120]

    def _read_chapter_assembled(self, slug: str, chapter_id: str) -> ChapterAssembledDocument | None:
        path = self.paths.chapter_assembled_path(slug, chapter_id)
        if not self.file_repository.exists(path):
            return None
        return ChapterAssembledDocument.model_validate(self.file_repository.read_json(path))

    def _write_volume_summaries(self, slug: str, document: VolumeSummariesMemoryDocument) -> None:
        self.file_repository.write_json(self.paths.volume_summaries_memory_path(slug), document.model_dump(mode="json"))

    def _write_book_summary(self, slug: str, document: BookSummaryMemoryDocument) -> None:
        self.file_repository.write_json(self.paths.book_summary_memory_path(slug), document.model_dump(mode="json"))
