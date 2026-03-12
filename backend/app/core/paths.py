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

    def plans_dir(self, slug: str) -> Path:
        return self.project_root(slug) / "plans"

    def drafts_dir(self, slug: str) -> Path:
        return self.project_root(slug) / "drafts"

    def memory_dir(self, slug: str) -> Path:
        return self.project_root(slug) / "memory"

    def meta_dir(self, slug: str) -> Path:
        return self.project_root(slug) / ".meta"

    def vectorstore_dir(self, slug: str) -> Path:
        return self.meta_dir(slug) / "vectorstore"
