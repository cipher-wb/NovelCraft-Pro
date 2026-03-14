from __future__ import annotations

import json
from pathlib import Path

import pytest

from backend.app.schemas.project import CreateProjectRequest


def _project_root(seed) -> Path:
    return seed["paths"].project_root(seed["manifest"].slug)


def _build_services(service_container):
    from backend.app.services.book_assembly_service import BookAssemblyService
    from backend.app.services.book_continuity_checks_service import BookContinuityChecksService
    from backend.app.services.book_checks_service import BookChecksService
    from backend.app.services.chapter_assembly_service import ChapterAssemblyService
    from backend.app.services.chapter_checks_service import ChapterChecksService
    from backend.app.services.checks_service import ChecksService
    from backend.app.services.context_bundle_service import ContextBundleService
    from backend.app.services.export_service import ExportService
    from backend.app.services.memory_service import MemoryService
    from backend.app.services.project_health_service import ProjectHealthService
    from backend.app.services.rebuild_service import RebuildService
    from backend.app.services.retrieval_service import RetrievalService
    from backend.app.services.scene_draft_service import SceneDraftService
    from backend.app.services.style_service import StyleService
    from backend.app.services.voice_constraint_builder import VoiceConstraintBuilder
    from backend.app.services.volume_assembly_service import VolumeAssemblyService
    from backend.app.services.volume_checks_service import VolumeChecksService

    paths = service_container["paths"]
    file_repository = service_container["file_repository"]
    sqlite_repository = service_container["sqlite_repository"]
    planner_service = service_container["planner_service"]
    bible_service = service_container["bible_service"]
    llm_gateway = service_container["llm_gateway"]

    style_service = StyleService(paths, file_repository, sqlite_repository)
    voice_constraint_builder = VoiceConstraintBuilder(style_service)
    retrieval_service = RetrievalService(paths, file_repository, sqlite_repository, planner_service)
    context_service = ContextBundleService(
        paths,
        file_repository,
        bible_service,
        planner_service,
        retrieval_service,
        voice_constraint_builder,
    )
    checks_service = ChecksService(paths, file_repository, sqlite_repository, bible_service, planner_service, context_service)
    memory_service = MemoryService(paths, file_repository, bible_service)
    draft_service = SceneDraftService(
        paths,
        file_repository,
        sqlite_repository,
        bible_service,
        planner_service,
        context_service,
        memory_service,
        checks_service,
        style_service,
        llm_gateway,
    )
    chapter_checks_service = ChapterChecksService(paths, file_repository, sqlite_repository, planner_service, draft_service)
    chapter_service = ChapterAssemblyService(
        paths,
        file_repository,
        sqlite_repository,
        planner_service,
        draft_service,
        memory_service,
        chapter_checks_service,
    )
    volume_checks_service = VolumeChecksService(paths, file_repository, sqlite_repository, planner_service)
    volume_service = VolumeAssemblyService(
        paths,
        file_repository,
        sqlite_repository,
        planner_service,
        chapter_service,
        memory_service,
        volume_checks_service,
    )
    book_checks_service = BookChecksService(paths, file_repository, sqlite_repository, planner_service)
    continuity_service = BookContinuityChecksService(
        paths,
        file_repository,
        sqlite_repository,
        bible_service,
        planner_service,
    )
    book_service = BookAssemblyService(
        paths,
        file_repository,
        sqlite_repository,
        planner_service,
        volume_service,
        memory_service,
        book_checks_service,
        continuity_service,
    )
    export_service = ExportService(
        paths,
        file_repository,
        sqlite_repository,
        planner_service,
    )
    rebuild_service = RebuildService(
        paths,
        file_repository,
        sqlite_repository,
        bible_service,
        planner_service,
        checks_service,
        chapter_checks_service,
        volume_checks_service,
        book_checks_service,
        continuity_service,
        chapter_service,
        volume_service,
        book_service,
    )
    health_service = ProjectHealthService(
        paths,
        file_repository,
        sqlite_repository,
        bible_service,
        planner_service,
    )
    return {
        "draft_service": draft_service,
        "chapter_service": chapter_service,
        "volume_service": volume_service,
        "book_service": book_service,
        "export_service": export_service,
        "rebuild_service": rebuild_service,
        "health_service": health_service,
    }


def _seed_multi_volume_project(service_container, *, volume_count: int = 2, chapters_per_volume: int = 2) -> dict[str, object]:
    project_service = service_container["project_service"]
    bible_service = service_container["bible_service"]
    planner_service = service_container["planner_service"]
    file_repository = service_container["file_repository"]
    paths = service_container["paths"]

    manifest, _ = project_service.create_project(
        CreateProjectRequest(
            title="Productization测试书",
            genre="都市异能",
            target_chapters=chapters_per_volume * volume_count,
            target_words=500_000,
        )
    )
    file_repository.write_json(
        paths.consultant_dossier_path(manifest.slug),
        {
            "dossier_id": "dossier_productization",
            "project_id": manifest.project_id,
            "high_concept": "都市修真长线升级",
            "subgenres": ["都市异能", "升级流"],
            "target_audience": ["男频爽文读者"],
            "selling_points": ["升级", "冲突"],
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

    outline = planner_service.generate_volumes(
        manifest.project_id,
        volume_count_hint=volume_count,
        chapters_per_volume_hint=chapters_per_volume,
    )
    planner_service.confirm_master_outline(manifest.project_id)
    volume_ids: list[str] = []
    chapter_ids_by_volume: dict[str, list[str]] = {}
    scene_ids_by_chapter: dict[str, list[str]] = {}
    for volume_ref in outline.volumes:
        volume_ids.append(volume_ref.volume_id)
        planner_service.confirm_volume(manifest.project_id, volume_ref.volume_id)
        chapters = planner_service.generate_chapters(manifest.project_id, volume_ref.volume_id)
        chapter_ids_by_volume[volume_ref.volume_id] = [chapter.chapter_id for chapter in chapters]
        for chapter in chapters:
            planner_service.confirm_chapter(manifest.project_id, chapter.chapter_id)
            scenes = planner_service.generate_scenes(manifest.project_id, chapter.chapter_id, scene_count_hint=2)
            scene_ids_by_chapter[chapter.chapter_id] = [scene.scene_id for scene in scenes]
            for scene in scenes:
                planner_service.confirm_scene(manifest.project_id, scene.scene_id)

    return {
        "manifest": manifest,
        "paths": paths,
        "planner_service": planner_service,
        "file_repository": file_repository,
        "volume_ids": volume_ids,
        "chapter_ids_by_volume": chapter_ids_by_volume,
        "scene_ids_by_chapter": scene_ids_by_chapter,
    }


def _accept_all_scenes(seed, services, *, volume_ids: list[str] | None = None) -> None:
    manifest = seed["manifest"]
    target_volumes = set(volume_ids or seed["volume_ids"])
    for volume_id in seed["volume_ids"]:
        if volume_id not in target_volumes:
            continue
        for chapter_id in seed["chapter_ids_by_volume"][volume_id]:
            for index, scene_id in enumerate(seed["scene_ids_by_chapter"][chapter_id]):
                draft = services["draft_service"].generate(
                    manifest.project_id,
                    scene_id,
                    "momentum" if index % 2 else "outline_strict",
                )
                services["draft_service"].accept(manifest.project_id, draft.draft_id)


def _finalize_all(seed, services) -> None:
    manifest = seed["manifest"]
    for volume_id in seed["volume_ids"]:
        for chapter_id in seed["chapter_ids_by_volume"][volume_id]:
            services["chapter_service"].assemble(manifest.project_id, chapter_id)
            services["chapter_service"].finalize(manifest.project_id, chapter_id)
        services["volume_service"].assemble(manifest.project_id, volume_id)
        services["volume_service"].finalize(manifest.project_id, volume_id)
    services["book_service"].assemble(manifest.project_id)
    services["book_service"].finalize(manifest.project_id)


def test_export_service_generates_unique_package_dirs_and_fixed_manifest(service_container) -> None:
    seed = _seed_multi_volume_project(service_container, volume_count=1, chapters_per_volume=1)
    services = _build_services(service_container)
    _accept_all_scenes(seed, services)
    _finalize_all(seed, services)

    project_id = seed["manifest"].project_id
    chapter_id = seed["chapter_ids_by_volume"][seed["volume_ids"][0]][0]
    scene_id = seed["scene_ids_by_chapter"][chapter_id][0]

    first = services["export_service"].export(project_id, scope="scene", target_id=scene_id, format="markdown_package")
    second = services["export_service"].export(project_id, scope="scene", target_id=scene_id, format="markdown_package")
    assert first.export_id != second.export_id
    assert first.relative_dir != second.relative_dir

    manifest_path = _project_root(seed) / first.relative_dir / "manifest.json"
    manifest_payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest_payload["export_id"] == first.export_id
    assert manifest_payload["scope"] == "scene"
    assert manifest_payload["target_id"] == scene_id
    assert manifest_payload["format"] == "markdown_package"
    assert manifest_payload["source_status"] == "accepted"
    assert "included_files" in manifest_payload
    assert "warnings" in manifest_payload
    assert (_project_root(seed) / first.relative_dir / "content.md").exists()

    book_export = services["export_service"].export(project_id, scope="book", target_id="book", format="json_package")
    book_manifest = json.loads((_project_root(seed) / book_export.relative_dir / "manifest.json").read_text(encoding="utf-8"))
    assert book_manifest["source_status"] == "finalized"
    assert "artifacts/assembled.json" in book_manifest["included_files"]


def test_rebuild_service_is_idempotent_and_only_recreates_missing_layers(service_container) -> None:
    seed = _seed_multi_volume_project(service_container, volume_count=1, chapters_per_volume=1)
    services = _build_services(service_container)
    _accept_all_scenes(seed, services)

    manifest = seed["manifest"]
    chapter_id = seed["chapter_ids_by_volume"][seed["volume_ids"][0]][0]
    scene_id = seed["scene_ids_by_chapter"][chapter_id][0]

    draft_manifest = services["draft_service"].get_scene_manifest(manifest.project_id, scene_id)
    accepted_draft = next(
        services["draft_service"].get_draft(manifest.project_id, item.draft_id)
        for item in draft_manifest.items
        if item.status == "accepted"
    )
    accepted_report_path = _project_root(seed) / accepted_draft.latest_check_report_path
    if accepted_report_path.exists():
        accepted_report_path.unlink()

    report_one = services["rebuild_service"].rebuild(manifest.project_id)
    assert report_one.targets == ["memory", "chapters", "volumes", "book", "checks"]
    assert report_one.overall_status in {"success", "partial"}
    assert (_project_root(seed) / "memory" / "accepted_scenes.json").exists()
    assert (_project_root(seed) / "memory" / "chapter_summaries.json").exists()
    assert (_project_root(seed) / "memory" / "character_state_summaries.json").exists()
    assert (_project_root(seed) / accepted_draft.latest_check_report_path).exists()

    chapter_artifact_path = service_container["paths"].chapter_assembled_path(manifest.slug, chapter_id)
    assert chapter_artifact_path.exists()

    report_two = services["rebuild_service"].rebuild(manifest.project_id)
    assert report_two.overall_status in {"success", "partial"}
    assert all(step.created_count == 0 for step in report_two.steps if step.target != "checks")
    assert all(step.updated_count == 0 for step in report_two.steps if step.target != "checks")


def test_project_health_service_is_read_only_and_uses_machine_codes(service_container) -> None:
    seed = _seed_multi_volume_project(service_container, volume_count=2, chapters_per_volume=1)
    services = _build_services(service_container)
    _accept_all_scenes(seed, services)
    _finalize_all(seed, services)

    manifest = seed["manifest"]
    book_path = service_container["paths"].book_assembled_path(manifest.slug)
    before = book_path.read_text(encoding="utf-8")

    replacement = services["draft_service"].generate(
        manifest.project_id,
        seed["scene_ids_by_chapter"][seed["chapter_ids_by_volume"][seed["volume_ids"][0]][0]][0],
        "momentum",
    )
    services["draft_service"].accept(manifest.project_id, replacement.draft_id)

    health = services["health_service"].build_report(manifest.project_id)
    after = book_path.read_text(encoding="utf-8")

    assert before == after
    assert health.book_artifact.status == "finalized"
    assert health.overall_status in {"warning", "blocked"}
    assert all(item.code for item in health.actionable_items)
    assert any(item.code in {"chapter_artifact_stale", "volume_artifact_stale", "book_artifact_stale", "missing_accepted_scene"} for item in health.actionable_items)
