from __future__ import annotations

from pathlib import Path

from backend.app.infra.vectorstore import VectorStoreStub


class VectorRepository:
    def __init__(self, root_dir: Path) -> None:
        self._store = VectorStoreStub(root_dir)

    def ensure_project_namespace(self, project_id: str) -> Path:
        return self._store.ensure_namespace(project_id)

    def reset_project_namespace(self, project_id: str) -> Path:
        return self._store.reset_namespace(project_id)
