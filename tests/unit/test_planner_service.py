from __future__ import annotations

from pathlib import Path

import pytest



def _build_draft_bible_context(workspace_tmp_dir: Path):
    from backend.app.core.config import Settings
    from backend.app.core.paths import AppPaths
    from backend.app.repositories.file_repository import FileRepository
    from backend.app.repositories.sqlite_repository import SQLiteRepository
    from backend.app.repositories.vector_repository import VectorRepository
    from backend.app.schemas.project import CreateProjectRequest
    from backend.app.services.bible_service import BibleService
    from backend.app.services.bootstrap_service import BootstrapService
    from backend.app.services.planner_service import PlannerService
    from backend.app.services.project_service import ProjectService

    data_root = workspace_tmp_dir / "data"
    projects_root = workspace_tmp_dir / "projects"
    settings = Settings(
        app_env="test",
        app_host="127.0.0.1",
        app_port=8000,
        data_root=data_root,
        projects_root=projects_root,
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
    bible_service = BibleService(paths, file_repository, sqlite_repository)
    planner_service = PlannerService(paths, file_repository, sqlite_repository, bible_service)

    manifest, _ = project_service.create_project(
        CreateProjectRequest(
            title="Planner测试书",
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
            "high_concept": "靠系统崛起",
            "subgenres": ["都市异能"],
            "target_audience": ["男频爽文读者"],
            "selling_points": ["升级", "打脸"],
            "protagonist_seed": {"summary": "隐忍型主角"},
            "golden_finger": {"summary": "系统"},
            "core_conflicts": ["隐世与俗世冲突"],
            "chapter_1_30_beats": [{"range": "1-10", "focus": "觉醒"}],
            "qa_transcript": [],
            "version": 1,
        },
    )
    bible_service.initialize_from_consultant(manifest.project_id)
    return manifest, planner_service



def _build_ready_bible_context(workspace_tmp_dir: Path):
    from backend.app.core.config import Settings
    from backend.app.core.paths import AppPaths
    from backend.app.repositories.file_repository import FileRepository
    from backend.app.repositories.sqlite_repository import SQLiteRepository
    from backend.app.repositories.vector_repository import VectorRepository
    from backend.app.schemas.project import CreateProjectRequest
    from backend.app.services.bible_service import BibleService
    from backend.app.services.bootstrap_service import BootstrapService
    from backend.app.services.planner_service import PlannerService
    from backend.app.services.project_service import ProjectService

    data_root = workspace_tmp_dir / "data"
    projects_root = workspace_tmp_dir / "projects"
    settings = Settings(
        app_env="test",
        app_host="127.0.0.1",
        app_port=8000,
        data_root=data_root,
        projects_root=projects_root,
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
    bible_service = BibleService(paths, file_repository, sqlite_repository)
    planner_service = PlannerService(paths, file_repository, sqlite_repository, bible_service)

    manifest, _ = project_service.create_project(
        CreateProjectRequest(
            title="Planner测试书",
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
            "high_concept": "靠系统崛起",
            "subgenres": ["都市异能"],
            "target_audience": ["男频爽文读者"],
            "selling_points": ["升级", "打脸"],
            "protagonist_seed": {"summary": "隐忍型主角"},
            "golden_finger": {"summary": "系统"},
            "core_conflicts": ["隐世与俗世冲突"],
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
    return manifest, planner_service



def test_generate_volumes_requires_ready_bible(workspace_tmp_dir: Path) -> None:
    manifest, planner_service = _build_draft_bible_context(workspace_tmp_dir)

    with pytest.raises(ValueError):
        planner_service.generate_volumes(manifest.project_id)



def test_generate_volumes_returns_conflict_when_outline_exists_and_overwrite_false(workspace_tmp_dir: Path) -> None:
    from backend.app.services.exceptions import ConflictError

    manifest, planner_service = _build_ready_bible_context(workspace_tmp_dir)
    planner_service.generate_volumes(manifest.project_id)

    with pytest.raises(ConflictError):
        planner_service.generate_volumes(manifest.project_id)



def test_confirm_master_outline_only_validates_outline_structure_and_volume_references(workspace_tmp_dir: Path) -> None:
    manifest, planner_service = _build_ready_bible_context(workspace_tmp_dir)
    outline = planner_service.generate_volumes(manifest.project_id)

    confirmed = planner_service.confirm_master_outline(manifest.project_id)

    assert confirmed.status == "ready"
    assert confirmed.volumes[0].volume_id == outline.volumes[0].volume_id



def test_generate_chapters_and_scenes_use_unique_numbers(workspace_tmp_dir: Path) -> None:
    manifest, planner_service = _build_ready_bible_context(workspace_tmp_dir)
    outline = planner_service.generate_volumes(manifest.project_id)
    first_volume_id = outline.volumes[0].volume_id
    planner_service.confirm_master_outline(manifest.project_id)
    planner_service.confirm_volume(manifest.project_id, first_volume_id)

    chapters = planner_service.generate_chapters(manifest.project_id, first_volume_id)
    assert len({chapter.chapter_no for chapter in chapters}) == len(chapters)

    planner_service.confirm_chapter(manifest.project_id, chapters[0].chapter_id)
    scenes = planner_service.generate_scenes(manifest.project_id, chapters[0].chapter_id)
    assert [scene.scene_no for scene in scenes] == list(range(1, len(scenes) + 1))
