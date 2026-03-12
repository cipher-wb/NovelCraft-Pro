from __future__ import annotations

from pathlib import Path
from typing import Any

from backend.app.core.paths import AppPaths
from backend.app.domain.models.common import utc_now
from backend.app.domain.models.project import StoryBible
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
            plans_dir / "volumes",
            plans_dir / "chapters",
            plans_dir / "scenes",
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
        empty_bible = StoryBible(
            bible_id=f"bible_{manifest_payload['project_id']}",
            project_id=manifest_payload["project_id"],
            updated_at=utc_now(),
        )
        self.file_repository.write_json(bible_dir / "story_bible.json", empty_bible.model_dump(mode="json"))
        self.file_repository.write_json(bible_dir / "characters.json", [])
        self.file_repository.write_json(bible_dir / "world.json", {"factions": [], "locations": []})
        self.file_repository.write_json(bible_dir / "power_system.json", {})
        self.file_repository.write_json(bible_dir / "voice_profile.json", {})
        self.file_repository.write_json(plans_dir / "master_outline.json", {"volumes": []})
        self.file_repository.write_json(memory_dir / "timeline.json", [])
        self.file_repository.write_json(memory_dir / "foreshadows.json", [])
        self.file_repository.write_json(memory_dir / "payoffs.json", [])

        return {
            "root": project_root,
            "consultant_dir": consultant_dir,
            "bible_dir": bible_dir,
            "plans_dir": plans_dir,
            "drafts_dir": drafts_dir,
            "memory_dir": memory_dir,
            "meta_dir": meta_dir,
        }
