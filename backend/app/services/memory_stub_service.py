from __future__ import annotations

import uuid

from backend.app.core.paths import AppPaths
from backend.app.domain.models.common import utc_now
from backend.app.domain.models.planning import ScenePlan
from backend.app.domain.models.writing import AcceptedSceneMemoryDocument, AcceptedSceneMemoryItem, SceneDraft
from backend.app.repositories.file_repository import FileRepository


class MemoryStubService:
    def __init__(self, paths: AppPaths, file_repository: FileRepository) -> None:
        self.paths = paths
        self.file_repository = file_repository

    def read_document(self, slug: str, project_id: str) -> AcceptedSceneMemoryDocument:
        path = self.paths.accepted_scenes_memory_path(slug)
        if self.file_repository.exists(path):
            return AcceptedSceneMemoryDocument.model_validate(self.file_repository.read_json(path))
        document = AcceptedSceneMemoryDocument(project_id=project_id, updated_at=utc_now())
        self.file_repository.write_json(path, document.model_dump(mode="json"))
        return document

    def ingest_accepted_scene(self, slug: str, draft: SceneDraft, scene: ScenePlan) -> AcceptedSceneMemoryItem:
        document = self.read_document(slug, draft.project_id)
        summary = draft.summary or self._fallback_summary(draft.content_md, scene.title)
        item = AcceptedSceneMemoryItem(
            memory_id=f"mem_{uuid.uuid4().hex[:12]}",
            scene_id=scene.scene_id,
            chapter_id=scene.chapter_id,
            volume_id=scene.volume_id,
            draft_id=draft.draft_id,
            chapter_no=draft.chapter_no,
            scene_no=draft.scene_no,
            scene_title=scene.title,
            scene_type=scene.scene_type,
            summary=summary,
            summary_source="draft_summary" if draft.summary else "heuristic_fallback",
            character_ids=scene.character_ids,
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
        self.file_repository.write_json(self.paths.accepted_scenes_memory_path(slug), document.model_dump(mode="json"))
        return item

    def _fallback_summary(self, content_md: str, title: str) -> str:
        text = " ".join(part.strip() for part in content_md.splitlines() if part.strip())
        if not text:
            return title
        return text[:120]
