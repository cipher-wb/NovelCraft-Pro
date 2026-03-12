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


@pytest.fixture()
def create_finalized_project(client: TestClient):
    def _create() -> dict[str, str]:
        project_response = client.post(
            "/api/projects",
            json={
                "title": "Bible API测试书",
                "genre": "都市异能",
                "target_chapters": 120,
                "target_words": 1_000_000,
            },
        )
        project = project_response.json()
        start = client.post(
            f"/api/projects/{project['project_id']}/consultant/sessions",
            json={
                "brief": "都市修仙打脸升级流",
                "preferred_subgenres": ["都市异能", "升级流"],
                "constraints": ["作者主导", "长线连载"],
            },
        )
        session_id = start.json()["session_id"]
        answers = {
            "market_hook": "社畜重生后靠功德系统在都市修仙打脸",
            "target_audience": "男频爽文读者",
            "protagonist_design": "隐忍型主角，前期受辱后快速崛起",
            "golden_finger_design": "功德兑换系统",
            "core_conflict_engine": "凡俗社会秩序与修真隐世势力冲突",
            "early_30_chapter_pacing": "前10章受辱觉醒，中10章立威，中后10章破局",
        }
        question = start.json()["current_question"]
        while question is not None:
            state = client.post(
                f"/api/consultant/sessions/{session_id}/answer",
                json={"question_id": question["question_id"], "answer": answers[question["question_id"]]},
            )
            question = state.json()["current_question"]
        finalize = client.post(f"/api/consultant/sessions/{session_id}/finalize")
        assert finalize.status_code == 200
        return {"project_id": project["project_id"], "slug": project["slug"]}

    return _create
