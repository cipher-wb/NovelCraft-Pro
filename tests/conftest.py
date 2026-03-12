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


@pytest.fixture()
def build_ready_scene_project(client: TestClient, create_finalized_project):
    def _build(*, confirm_scene: bool = True) -> dict[str, object]:
        project = create_finalized_project()
        project_id = project["project_id"]

        assert client.post(f"/api/projects/{project_id}/bible/from-consultant").status_code == 201
        assert client.post(f"/api/projects/{project_id}/characters/confirm").status_code == 200
        assert client.post(f"/api/projects/{project_id}/bible/world/confirm").status_code == 200
        assert client.post(f"/api/projects/{project_id}/bible/power-system/confirm").status_code == 200
        assert client.post(f"/api/projects/{project_id}/bible/story-bible/confirm").status_code == 200

        outline = client.post(f"/api/projects/{project_id}/plans/volumes/generate")
        assert outline.status_code == 201
        volume_id = outline.json()["volumes"][0]["volume_id"]

        assert client.post(f"/api/projects/{project_id}/plans/master-outline/confirm").status_code == 200
        assert client.post(f"/api/projects/{project_id}/plans/volumes/{volume_id}/confirm").status_code == 200

        chapters = client.post(f"/api/projects/{project_id}/plans/volumes/{volume_id}/chapters/generate")
        assert chapters.status_code == 201
        chapter_id = chapters.json()["items"][0]["chapter_id"]
        assert client.post(f"/api/projects/{project_id}/plans/chapters/{chapter_id}/confirm").status_code == 200

        scenes = client.post(f"/api/projects/{project_id}/plans/chapters/{chapter_id}/scenes/generate")
        assert scenes.status_code == 201
        scene_items = scenes.json()["items"]
        scene_id = scene_items[0]["scene_id"]
        if confirm_scene:
            assert client.post(f"/api/projects/{project_id}/plans/scenes/{scene_id}/confirm").status_code == 200

        return {
            "project_id": project_id,
            "slug": project["slug"],
            "volume_id": volume_id,
            "chapter_id": chapter_id,
            "scene_id": scene_id,
            "scene_ids": [item["scene_id"] for item in scene_items],
        }

    return _build


@pytest.fixture()
def service_container(temp_roots: dict[str, Path]):
    from backend.app.core.config import Settings
    from backend.app.core.paths import AppPaths
    from backend.app.infra.llm_gateway import MockLLMGateway
    from backend.app.repositories.file_repository import FileRepository
    from backend.app.repositories.sqlite_repository import SQLiteRepository
    from backend.app.repositories.vector_repository import VectorRepository
    from backend.app.schemas.project import CreateProjectRequest
    from backend.app.services.bible_service import BibleService
    from backend.app.services.bootstrap_service import BootstrapService
    from backend.app.services.consultant_service import ConsultantService
    from backend.app.services.planner_service import PlannerService
    from backend.app.services.project_service import ProjectService

    settings = Settings(
        app_env="test",
        app_host="127.0.0.1",
        app_port=8000,
        data_root=temp_roots["data_root"],
        projects_root=temp_roots["projects_root"],
        llm_mode="mock",
        openai_base_url="https://api.openai.com/v1",
        openai_api_key="",
    )
    paths = AppPaths(settings)
    paths.ensure_runtime_dirs()
    file_repository = FileRepository()
    sqlite_repository = SQLiteRepository(paths.app_db_path)
    sqlite_repository.initialize()
    bootstrap_service = BootstrapService(paths, file_repository)
    vector_repository = VectorRepository(paths.data_root / "vectorstore_stub")
    project_service = ProjectService(paths, file_repository, sqlite_repository, vector_repository, bootstrap_service)
    consultant_service = ConsultantService(paths, file_repository, sqlite_repository)
    bible_service = BibleService(paths, file_repository, sqlite_repository)
    planner_service = PlannerService(paths, file_repository, sqlite_repository, bible_service)
    llm_gateway = MockLLMGateway()

    def seed_project(*, ready_scene: bool = True, scene_count_hint: int = 2) -> dict[str, object]:
        manifest, _ = project_service.create_project(
            CreateProjectRequest(
                title="Draft测试书",
                genre="都市异能",
                target_chapters=60,
                target_words=600_000,
            )
        )
        file_repository.write_json(
            paths.consultant_dossier_path(manifest.slug),
            {
                "dossier_id": "dossier_test",
                "project_id": manifest.project_id,
                "high_concept": "靠系统在都市中逆袭崛起",
                "subgenres": ["都市异能", "升级流"],
                "target_audience": ["男频爽文读者"],
                "selling_points": ["升级", "打脸"],
                "protagonist_seed": {"summary": "隐忍后爆发的主角"},
                "golden_finger": {"summary": "功德兑换系统"},
                "core_conflicts": ["隐世势力与现代秩序冲突"],
                "chapter_1_30_beats": [{"range": "1-10", "focus": "觉醒"}],
                "qa_transcript": [],
                "version": 1,
            },
        )
        bible_service.initialize_from_consultant(manifest.project_id)
        bible_service.confirm_characters(manifest.project_id)
        bible_service.confirm_world(manifest.project_id)
        bible_service.confirm_power_system(manifest.project_id)
        bible_service.confirm_story_bible(manifest.project_id)

        outline = planner_service.generate_volumes(manifest.project_id, volume_count_hint=1, chapters_per_volume_hint=2)
        volume_id = outline.volumes[0].volume_id
        planner_service.confirm_master_outline(manifest.project_id)
        planner_service.confirm_volume(manifest.project_id, volume_id)
        chapters = planner_service.generate_chapters(manifest.project_id, volume_id)
        chapter_id = chapters[0].chapter_id
        planner_service.confirm_chapter(manifest.project_id, chapter_id)
        scenes = planner_service.generate_scenes(manifest.project_id, chapter_id, scene_count_hint=scene_count_hint)
        scene_id = scenes[0].scene_id
        if ready_scene:
            planner_service.confirm_scene(manifest.project_id, scene_id)

        return {
            "manifest": manifest,
            "paths": paths,
            "file_repository": file_repository,
            "sqlite_repository": sqlite_repository,
            "project_service": project_service,
            "consultant_service": consultant_service,
            "bible_service": bible_service,
            "planner_service": planner_service,
            "llm_gateway": llm_gateway,
            "volume_id": volume_id,
            "chapter_id": chapter_id,
            "scene_id": scene_id,
            "scenes": scenes,
        }

    return {
        "settings": settings,
        "paths": paths,
        "file_repository": file_repository,
        "sqlite_repository": sqlite_repository,
        "project_service": project_service,
        "consultant_service": consultant_service,
        "bible_service": bible_service,
        "planner_service": planner_service,
        "llm_gateway": llm_gateway,
        "seed_project": seed_project,
    }
