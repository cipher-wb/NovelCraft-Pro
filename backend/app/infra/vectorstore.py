from __future__ import annotations

import shutil
from pathlib import Path


class VectorStoreStub:
    def __init__(self, root_dir: Path) -> None:
        self.root_dir = root_dir

    def ensure_namespace(self, project_id: str) -> Path:
        namespace_dir = self.root_dir / project_id
        namespace_dir.mkdir(parents=True, exist_ok=True)
        return namespace_dir

    def reset_namespace(self, project_id: str) -> Path:
        namespace_dir = self.root_dir / project_id
        shutil.rmtree(namespace_dir, ignore_errors=True)
        namespace_dir.mkdir(parents=True, exist_ok=True)
        return namespace_dir
