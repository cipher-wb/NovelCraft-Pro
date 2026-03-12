from __future__ import annotations

from pathlib import Path

from backend.app.core.config import Settings


class AppPaths:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    @property
    def data_root(self) -> Path:
        return self.settings.data_root

    @property
    def projects_root(self) -> Path:
        return self.settings.projects_root

    @property
    def app_db_path(self) -> Path:
        return self.data_root / "app.db"

    def ensure_runtime_dirs(self) -> None:
        self.data_root.mkdir(parents=True, exist_ok=True)
        self.projects_root.mkdir(parents=True, exist_ok=True)

    def project_root(self, slug: str) -> Path:
        return self.projects_root / slug

    def project_manifest_path(self, slug: str) -> Path:
        return self.project_root(slug) / "project.json"

    def consultant_dir(self, slug: str) -> Path:
        return self.project_root(slug) / "consultant"

    def consultant_sessions_dir(self, slug: str) -> Path:
        return self.consultant_dir(slug) / "sessions"

    def consultant_dossier_path(self, slug: str) -> Path:
        return self.consultant_dir(slug) / "dossier.json"

    def bible_dir(self, slug: str) -> Path:
        return self.project_root(slug) / "bible"

    def story_bible_path(self, slug: str) -> Path:
        return self.bible_dir(slug) / "story_bible.json"

    def characters_path(self, slug: str) -> Path:
        return self.bible_dir(slug) / "characters.json"

    def world_path(self, slug: str) -> Path:
        return self.bible_dir(slug) / "world.json"

    def power_system_path(self, slug: str) -> Path:
        return self.bible_dir(slug) / "power_system.json"

    def plans_dir(self, slug: str) -> Path:
        return self.project_root(slug) / "plans"

    def master_outline_path(self, slug: str) -> Path:
        return self.plans_dir(slug) / "master_outline.json"

    def volumes_dir(self, slug: str) -> Path:
        return self.plans_dir(slug) / "volumes"

    def chapters_dir(self, slug: str) -> Path:
        return self.plans_dir(slug) / "chapters"

    def scenes_dir(self, slug: str) -> Path:
        return self.plans_dir(slug) / "scenes"

    def volume_plan_path(self, slug: str, volume_no: int) -> Path:
        return self.volumes_dir(slug) / f"volume-{volume_no:03d}.json"

    def chapter_plan_path(self, slug: str, chapter_no: int) -> Path:
        return self.chapters_dir(slug) / f"chapter-{chapter_no:04d}.json"

    def scene_plan_path(self, slug: str, chapter_no: int, scene_no: int) -> Path:
        return self.scenes_dir(slug) / f"chapter-{chapter_no:04d}-scene-{scene_no:03d}.json"

    def drafts_dir(self, slug: str) -> Path:
        return self.project_root(slug) / "drafts"

    def memory_dir(self, slug: str) -> Path:
        return self.project_root(slug) / "memory"

    def meta_dir(self, slug: str) -> Path:
        return self.project_root(slug) / ".meta"

    def vectorstore_dir(self, slug: str) -> Path:
        return self.meta_dir(slug) / "vectorstore"
