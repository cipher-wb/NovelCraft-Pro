from __future__ import annotations

from pathlib import Path



def _build_context(workspace_tmp_dir: Path):
    from backend.app.core.config import Settings
    from backend.app.core.paths import AppPaths
    from backend.app.repositories.file_repository import FileRepository
    from backend.app.repositories.sqlite_repository import SQLiteRepository
    from backend.app.repositories.vector_repository import VectorRepository
    from backend.app.schemas.project import CreateProjectRequest
    from backend.app.services.bible_service import BibleService
    from backend.app.services.bootstrap_service import BootstrapService
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

    manifest, _ = project_service.create_project(
        CreateProjectRequest(
            title="Phase2测试书",
            genre="都市异能",
            target_chapters=120,
            target_words=1_000_000,
        )
    )
    dossier_payload = {
        "dossier_id": "dossier_test",
        "project_id": manifest.project_id,
        "high_concept": "社畜靠系统在都市逆袭",
        "subgenres": ["都市异能", "升级流"],
        "target_audience": ["男频爽文读者"],
        "selling_points": ["系统升级", "打脸反派"],
        "protagonist_seed": {"summary": "隐忍型主角"},
        "golden_finger": {"summary": "功德兑换系统"},
        "core_conflicts": ["现代社会与隐世势力冲突"],
        "chapter_1_30_beats": [{"range": "1-10", "focus": "觉醒"}],
        "qa_transcript": [],
        "version": 1,
    }
    file_repository.write_json(paths.consultant_dossier_path(manifest.slug), dossier_payload)
    return manifest, paths, file_repository, bible_service



def test_initialize_from_consultant_builds_bible_documents(workspace_tmp_dir: Path) -> None:
    manifest, paths, file_repository, bible_service = _build_context(workspace_tmp_dir)

    aggregate = bible_service.initialize_from_consultant(manifest.project_id)

    assert aggregate.story_bible.project_id == manifest.project_id
    assert aggregate.story_bible.status == "draft"
    assert aggregate.characters.project_id == manifest.project_id
    assert len(aggregate.characters.items) == 1
    assert aggregate.world.status == "draft"
    assert aggregate.power_system.status == "draft"
    assert file_repository.exists(paths.story_bible_path(manifest.slug))
    assert file_repository.exists(paths.characters_path(manifest.slug))



def test_character_mutation_marks_character_document_draft(workspace_tmp_dir: Path) -> None:
    manifest, _, _, bible_service = _build_context(workspace_tmp_dir)
    bible_service.initialize_from_consultant(manifest.project_id)
    bible_service.confirm_characters(manifest.project_id)

    bible_service.create_character(
        manifest.project_id,
        {
            "name": "新角色",
            "role": "support",
            "is_protagonist": False,
            "traits": ["冷静"],
        },
    )

    aggregate = bible_service.get_bible_aggregate(manifest.project_id)
    assert aggregate.characters.status == "draft"



def test_update_story_bible_marks_existing_master_outline_stale(workspace_tmp_dir: Path) -> None:
    manifest, paths, file_repository, bible_service = _build_context(workspace_tmp_dir)
    bible_service.initialize_from_consultant(manifest.project_id)
    file_repository.write_json(
        paths.master_outline_path(manifest.slug),
        {
            "project_id": manifest.project_id,
            "status": "ready",
            "version": 1,
            "updated_at": "2026-03-12T00:00:00Z",
            "source_bible_version": 1,
            "total_volumes": 0,
            "active_volume_id": None,
            "volumes": [],
        },
    )

    bible_service.update_story_bible(
        manifest.project_id,
        {"story_promise": "新的故事承诺"},
        partial=True,
    )

    outline_payload = file_repository.read_json(paths.master_outline_path(manifest.slug))
    assert outline_payload["status"] == "stale"



def test_confirm_story_bible_requires_featured_references(workspace_tmp_dir: Path) -> None:
    manifest, _, _, bible_service = _build_context(workspace_tmp_dir)
    bible_service.initialize_from_consultant(manifest.project_id)
    bible_service.update_story_bible(
        manifest.project_id,
        {"featured_faction_ids": ["missing_faction"]},
        partial=True,
    )

    import pytest

    with pytest.raises(ValueError):
        bible_service.confirm_story_bible(manifest.project_id)
