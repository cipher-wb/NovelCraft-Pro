from __future__ import annotations

from pathlib import Path
from typing import Any

from backend.app.core.paths import AppPaths
from backend.app.domain.models.common import utc_now
from backend.app.domain.models.planning import MasterOutlineDocument
from backend.app.domain.models.project import CharacterDocument, PowerSystemDocument, StoryBible, WorldDocument
from backend.app.domain.models.writing import AcceptedSceneMemoryDocument
from backend.app.repositories.file_repository import FileRepository


class BootstrapService:
    def __init__(self, paths: AppPaths, file_repository: FileRepository) -> None:
        self.paths = paths
        self.file_repository = file_repository

    def initialize_project_structure(self, slug: str, manifest_payload: dict[str, Any]) -> dict[str, Path]:
        project_root = self.paths.project_root(slug)
        consultant_dir = self.paths.consultant_dir(slug)
        consultant_sessions_dir = self.paths.consultant_sessions_dir(slug)
        bible_dir = self.paths.bible_dir(slug)
        plans_dir = self.paths.plans_dir(slug)
        drafts_dir = self.paths.drafts_dir(slug)
        memory_dir = self.paths.memory_dir(slug)
        meta_dir = self.paths.meta_dir(slug)
        vectorstore_dir = self.paths.vectorstore_dir(slug)

        dirs = [
            project_root,
            consultant_dir,
            consultant_sessions_dir,
            bible_dir,
            plans_dir,
            self.paths.volumes_dir(slug),
            self.paths.chapters_dir(slug),
            self.paths.scenes_dir(slug),
            drafts_dir,
            drafts_dir / "chapters",
            drafts_dir / "scenes",
            memory_dir,
            memory_dir / "states",
            meta_dir,
            vectorstore_dir,
        ]
        for directory in dirs:
            self.file_repository.ensure_dir(directory)

        self.file_repository.write_json(self.paths.project_manifest_path(slug), manifest_payload)
        now = utc_now()
        empty_bible = StoryBible(
            bible_id=f"bible_{manifest_payload['project_id']}",
            project_id=manifest_payload["project_id"],
            title=manifest_payload["title"],
            genre=manifest_payload["genre"],
            updated_at=now,
        )
        self.file_repository.write_json(self.paths.story_bible_path(slug), empty_bible.model_dump(mode="json"))
        self.file_repository.write_json(
            self.paths.characters_path(slug),
            CharacterDocument(project_id=manifest_payload["project_id"], updated_at=now).model_dump(mode="json"),
        )
        self.file_repository.write_json(
            self.paths.world_path(slug),
            WorldDocument(project_id=manifest_payload["project_id"], updated_at=now).model_dump(mode="json"),
        )
        self.file_repository.write_json(
            self.paths.power_system_path(slug),
            PowerSystemDocument(project_id=manifest_payload["project_id"], updated_at=now).model_dump(mode="json"),
        )
        self.file_repository.write_json(bible_dir / "voice_profile.json", {})
        self.file_repository.write_json(
            self.paths.master_outline_path(slug),
            MasterOutlineDocument(project_id=manifest_payload["project_id"], updated_at=now).model_dump(mode="json"),
        )
        self.file_repository.write_json(memory_dir / "timeline.json", [])
        self.file_repository.write_json(memory_dir / "foreshadows.json", [])
        self.file_repository.write_json(memory_dir / "payoffs.json", [])
        self.file_repository.write_json(
            self.paths.accepted_scenes_memory_path(slug),
            AcceptedSceneMemoryDocument(project_id=manifest_payload["project_id"], updated_at=now).model_dump(mode="json"),
        )

        return {
            "root": project_root,
            "consultant_dir": consultant_dir,
            "bible_dir": bible_dir,
            "plans_dir": plans_dir,
            "drafts_dir": drafts_dir,
            "memory_dir": memory_dir,
            "meta_dir": meta_dir,
        }
