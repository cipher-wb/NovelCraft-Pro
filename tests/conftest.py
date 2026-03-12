from __future__ import annotations

import os
import shutil
import uuid
from pathlib import Path

import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def workspace_tmp_dir() -> Path:
    root = Path.cwd() / "test_sandbox" / uuid.uuid4().hex
    root.mkdir(parents=True, exist_ok=True)
    try:
        yield root
    finally:
        shutil.rmtree(root, ignore_errors=True)


@pytest.fixture()
def temp_roots(workspace_tmp_dir: Path, monkeypatch: pytest.MonkeyPatch) -> dict[str, Path]:
    data_root = workspace_tmp_dir / "data"
    projects_root = workspace_tmp_dir / "projects"
    data_root.mkdir(parents=True, exist_ok=True)
    projects_root.mkdir(parents=True, exist_ok=True)

    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("APP_HOST", "127.0.0.1")
    monkeypatch.setenv("APP_PORT", "8000")
    monkeypatch.setenv("DATA_ROOT", str(data_root))
    monkeypatch.setenv("PROJECTS_ROOT", str(projects_root))
    monkeypatch.setenv("LLM_MODE", "mock")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setenv("OPENAI_BASE_URL", "https://api.openai.com/v1")

    return {"data_root": data_root, "projects_root": projects_root}


@pytest.fixture()
def client(temp_roots: dict[str, Path]) -> TestClient:
    os.environ["DATA_ROOT"] = str(temp_roots["data_root"])
    os.environ["PROJECTS_ROOT"] = str(temp_roots["projects_root"])

    from backend.app.main import create_app

    return TestClient(create_app())
