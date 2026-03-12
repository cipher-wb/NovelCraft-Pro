from __future__ import annotations

from pathlib import Path

import pytest


def _build_planner_context(workspace_tmp_dir: Path, *, ready_bible: bool) -> tuple:
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
    if ready_bible:
        bible_service.confirm_characters(manifest.project_id)
        bible_service.confirm_world(manifest.project_id)
        bible_service.confirm_power_system(manifest.project_id)
        bible_service.confirm_story_bible(manifest.project_id)
    return manifest, paths, file_repository, bible_service, planner_service


def test_generate_volumes_requires_ready_bible(workspace_tmp_dir: Path) -> None:
    manifest, _, _, _, planner_service = _build_planner_context(workspace_tmp_dir, ready_bible=False)

    with pytest.raises(ValueError):
        planner_service.generate_volumes(manifest.project_id)


def test_generate_volumes_returns_conflict_when_outline_exists_and_overwrite_false(workspace_tmp_dir: Path) -> None:
    from backend.app.services.exceptions import ConflictError

    manifest, _, _, _, planner_service = _build_planner_context(workspace_tmp_dir, ready_bible=True)
    planner_service.generate_volumes(manifest.project_id)

    with pytest.raises(ConflictError):
        planner_service.generate_volumes(manifest.project_id)


def test_master_outline_reads_legacy_status_and_rewrites_outline_status(workspace_tmp_dir: Path) -> None:
    manifest, paths, file_repository, _, planner_service = _build_planner_context(workspace_tmp_dir, ready_bible=False)
    file_repository.write_json(
        paths.master_outline_path(manifest.slug),
        {
            "project_id": manifest.project_id,
            "status": "draft",
            "version": 1,
            "updated_at": "2026-03-12T00:00:00Z",
            "source_bible_version": 0,
            "total_volumes": 0,
            "active_volume_id": None,
            "volumes": [],
        },
    )

    outline = planner_service.get_master_outline(manifest.project_id)
    assert outline.outline_status == "draft"

    confirmed = planner_service.confirm_master_outline(manifest.project_id)
    assert confirmed.outline_status == "ready"

    payload = file_repository.read_json(paths.master_outline_path(manifest.slug))
    assert payload["outline_status"] == "ready"
    assert "status" not in payload


def test_confirm_master_outline_only_validates_outline_structure_and_volume_references(workspace_tmp_dir: Path) -> None:
    manifest, _, _, _, planner_service = _build_planner_context(workspace_tmp_dir, ready_bible=True)
    outline = planner_service.generate_volumes(manifest.project_id)

    confirmed = planner_service.confirm_master_outline(manifest.project_id)

    assert confirmed.outline_status == "ready"
    assert confirmed.volumes[0].volume_id == outline.volumes[0].volume_id
    assert planner_service.get_volume(manifest.project_id, outline.volumes[0].volume_id).status == "draft"


def test_generate_chapters_and_scenes_use_unique_numbers(workspace_tmp_dir: Path) -> None:
    manifest, _, _, _, planner_service = _build_planner_context(workspace_tmp_dir, ready_bible=True)
    outline = planner_service.generate_volumes(manifest.project_id, volume_count_hint=2, chapters_per_volume_hint=2)
    first_volume_id = outline.volumes[0].volume_id
    planner_service.confirm_master_outline(manifest.project_id)
    planner_service.confirm_volume(manifest.project_id, first_volume_id)

    chapters = planner_service.generate_chapters(manifest.project_id, first_volume_id)
    assert len({chapter.chapter_no for chapter in chapters}) == len(chapters)

    planner_service.confirm_chapter(manifest.project_id, chapters[0].chapter_id)
    scenes = planner_service.generate_scenes(manifest.project_id, chapters[0].chapter_id)
    assert [scene.scene_no for scene in scenes] == list(range(1, len(scenes) + 1))


def test_generate_chapters_returns_conflict_when_targets_exist_and_overwrite_false(workspace_tmp_dir: Path) -> None:
    from backend.app.services.exceptions import ConflictError

    manifest, _, _, _, planner_service = _build_planner_context(workspace_tmp_dir, ready_bible=True)
    outline = planner_service.generate_volumes(manifest.project_id, volume_count_hint=1, chapters_per_volume_hint=2)
    volume_id = outline.volumes[0].volume_id
    planner_service.confirm_master_outline(manifest.project_id)
    planner_service.confirm_volume(manifest.project_id, volume_id)
    planner_service.generate_chapters(manifest.project_id, volume_id)

    with pytest.raises(ConflictError):
        planner_service.generate_chapters(manifest.project_id, volume_id)


def test_generate_scenes_returns_conflict_when_targets_exist_and_overwrite_false(workspace_tmp_dir: Path) -> None:
    from backend.app.services.exceptions import ConflictError

    manifest, _, _, _, planner_service = _build_planner_context(workspace_tmp_dir, ready_bible=True)
    outline = planner_service.generate_volumes(manifest.project_id, volume_count_hint=1, chapters_per_volume_hint=2)
    volume_id = outline.volumes[0].volume_id
    planner_service.confirm_master_outline(manifest.project_id)
    planner_service.confirm_volume(manifest.project_id, volume_id)
    chapters = planner_service.generate_chapters(manifest.project_id, volume_id)
    chapter_id = chapters[0].chapter_id
    planner_service.confirm_chapter(manifest.project_id, chapter_id)
    planner_service.generate_scenes(manifest.project_id, chapter_id, scene_count_hint=2)

    with pytest.raises(ConflictError):
        planner_service.generate_scenes(manifest.project_id, chapter_id)


def test_update_volume_rejects_duplicate_volume_no(workspace_tmp_dir: Path) -> None:
    manifest, _, _, _, planner_service = _build_planner_context(workspace_tmp_dir, ready_bible=True)
    outline = planner_service.generate_volumes(manifest.project_id, volume_count_hint=2, chapters_per_volume_hint=2)

    with pytest.raises(ValueError):
        planner_service.update_volume(manifest.project_id, outline.volumes[1].volume_id, {"volume_no": 1})


def test_update_chapter_rejects_duplicate_chapter_no(workspace_tmp_dir: Path) -> None:
    manifest, _, _, _, planner_service = _build_planner_context(workspace_tmp_dir, ready_bible=True)
    outline = planner_service.generate_volumes(manifest.project_id, volume_count_hint=1, chapters_per_volume_hint=2)
    volume_id = outline.volumes[0].volume_id
    planner_service.confirm_master_outline(manifest.project_id)
    planner_service.confirm_volume(manifest.project_id, volume_id)
    chapters = planner_service.generate_chapters(manifest.project_id, volume_id)

    with pytest.raises(ValueError):
        planner_service.update_chapter(manifest.project_id, chapters[1].chapter_id, {"chapter_no": chapters[0].chapter_no})


def test_update_scene_rejects_duplicate_scene_no(workspace_tmp_dir: Path) -> None:
    manifest, _, _, _, planner_service = _build_planner_context(workspace_tmp_dir, ready_bible=True)
    outline = planner_service.generate_volumes(manifest.project_id, volume_count_hint=1, chapters_per_volume_hint=2)
    volume_id = outline.volumes[0].volume_id
    planner_service.confirm_master_outline(manifest.project_id)
    planner_service.confirm_volume(manifest.project_id, volume_id)
    chapters = planner_service.generate_chapters(manifest.project_id, volume_id)
    chapter_id = chapters[0].chapter_id
    planner_service.confirm_chapter(manifest.project_id, chapter_id)
    scenes = planner_service.generate_scenes(manifest.project_id, chapter_id, scene_count_hint=2)

    with pytest.raises(ValueError):
        planner_service.update_scene(manifest.project_id, scenes[1].scene_id, {"scene_no": scenes[0].scene_no})


def test_valid_volume_renumber_updates_outline_refs_and_child_volume_numbers(workspace_tmp_dir: Path) -> None:
    manifest, paths, _, _, planner_service = _build_planner_context(workspace_tmp_dir, ready_bible=True)
    outline = planner_service.generate_volumes(manifest.project_id, volume_count_hint=2, chapters_per_volume_hint=2)
    volume_id = outline.volumes[1].volume_id
    planner_service.confirm_master_outline(manifest.project_id)
    planner_service.confirm_volume(manifest.project_id, volume_id)
    chapters = planner_service.generate_chapters(manifest.project_id, volume_id)

    updated = planner_service.update_volume(manifest.project_id, volume_id, {"volume_no": 9})

    assert updated.volume_no == 9
    assert paths.volume_plan_path(manifest.slug, 9).exists()
    assert not paths.volume_plan_path(manifest.slug, 2).exists()
    outline_payload = planner_service.get_master_outline(manifest.project_id)
    assert outline_payload.outline_status == "stale"
    assert any(ref.volume_id == volume_id and ref.volume_no == 9 for ref in outline_payload.volumes)
    reloaded_chapter = planner_service.get_chapter(manifest.project_id, chapters[0].chapter_id)
    assert reloaded_chapter.volume_no == 9


def test_valid_chapter_renumber_updates_scene_paths_and_stale_chain(workspace_tmp_dir: Path) -> None:
    manifest, paths, _, _, planner_service = _build_planner_context(workspace_tmp_dir, ready_bible=True)
    outline = planner_service.generate_volumes(manifest.project_id, volume_count_hint=1, chapters_per_volume_hint=2)
    volume_id = outline.volumes[0].volume_id
    planner_service.confirm_master_outline(manifest.project_id)
    planner_service.confirm_volume(manifest.project_id, volume_id)
    chapters = planner_service.generate_chapters(manifest.project_id, volume_id)
    chapter_id = chapters[0].chapter_id
    planner_service.confirm_chapter(manifest.project_id, chapter_id)
    scenes = planner_service.generate_scenes(manifest.project_id, chapter_id, scene_count_hint=2)

    updated = planner_service.update_chapter(manifest.project_id, chapter_id, {"chapter_no": 99})

    assert updated.chapter_no == 99
    assert paths.chapter_plan_path(manifest.slug, 99).exists()
    assert not paths.chapter_plan_path(manifest.slug, chapters[0].chapter_no).exists()
    assert paths.scene_plan_path(manifest.slug, 99, 1).exists()
    assert not paths.scene_plan_path(manifest.slug, chapters[0].chapter_no, scenes[0].scene_no).exists()
    outline_payload = planner_service.get_master_outline(manifest.project_id)
    assert outline_payload.outline_status == "stale"
    assert planner_service.get_volume(manifest.project_id, volume_id).status == "stale"


def test_valid_scene_renumber_updates_scene_path_and_parent_stale_chain(workspace_tmp_dir: Path) -> None:
    manifest, paths, _, _, planner_service = _build_planner_context(workspace_tmp_dir, ready_bible=True)
    outline = planner_service.generate_volumes(manifest.project_id, volume_count_hint=1, chapters_per_volume_hint=2)
    volume_id = outline.volumes[0].volume_id
    planner_service.confirm_master_outline(manifest.project_id)
    planner_service.confirm_volume(manifest.project_id, volume_id)
    chapters = planner_service.generate_chapters(manifest.project_id, volume_id)
    chapter_id = chapters[0].chapter_id
    planner_service.confirm_chapter(manifest.project_id, chapter_id)
    scenes = planner_service.generate_scenes(manifest.project_id, chapter_id, scene_count_hint=2)

    updated = planner_service.update_scene(manifest.project_id, scenes[1].scene_id, {"scene_no": 9})

    assert updated.scene_no == 9
    assert paths.scene_plan_path(manifest.slug, chapters[0].chapter_no, 9).exists()
    assert not paths.scene_plan_path(manifest.slug, chapters[0].chapter_no, scenes[1].scene_no).exists()
    assert planner_service.get_master_outline(manifest.project_id).outline_status == "stale"
    assert planner_service.get_volume(manifest.project_id, volume_id).status == "stale"
    assert planner_service.get_chapter(manifest.project_id, chapter_id).status == "stale"


def test_update_volume_marks_outline_and_descendants_stale(workspace_tmp_dir: Path) -> None:
    manifest, _, _, _, planner_service = _build_planner_context(workspace_tmp_dir, ready_bible=True)
    outline = planner_service.generate_volumes(manifest.project_id, volume_count_hint=1, chapters_per_volume_hint=2)
    volume_id = outline.volumes[0].volume_id
    planner_service.confirm_master_outline(manifest.project_id)
    planner_service.confirm_volume(manifest.project_id, volume_id)
    chapters = planner_service.generate_chapters(manifest.project_id, volume_id)
    chapter_id = chapters[0].chapter_id
    planner_service.confirm_chapter(manifest.project_id, chapter_id)
    scenes = planner_service.generate_scenes(manifest.project_id, chapter_id, scene_count_hint=2)
    planner_service.confirm_scene(manifest.project_id, scenes[0].scene_id)

    planner_service.update_volume(manifest.project_id, volume_id, {"summary": "卷摘要更新"})

    assert planner_service.get_master_outline(manifest.project_id).outline_status == "stale"
    assert planner_service.get_chapter(manifest.project_id, chapter_id).status == "stale"
    assert planner_service.get_scene(manifest.project_id, scenes[0].scene_id).status == "stale"
