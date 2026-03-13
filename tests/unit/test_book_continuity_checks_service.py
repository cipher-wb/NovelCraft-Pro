from __future__ import annotations

import json
from pathlib import Path

import pytest

from backend.app.schemas.project import CreateProjectRequest
from backend.app.services.exceptions import ConflictError


def _build_services(service_container):
    from backend.app.services.book_assembly_service import BookAssemblyService
    from backend.app.services.book_checks_service import BookChecksService
    from backend.app.services.book_continuity_checks_service import BookContinuityChecksService
    from backend.app.services.chapter_assembly_service import ChapterAssemblyService
    from backend.app.services.chapter_checks_service import ChapterChecksService
    from backend.app.services.checks_service import ChecksService
    from backend.app.services.context_bundle_service import ContextBundleService
    from backend.app.services.memory_service import MemoryService
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
    return draft_service, chapter_service, volume_service, book_service, continuity_service


def _project_root(seed) -> Path:
    return seed["paths"].project_root(seed["manifest"].slug)


def _seed_multi_volume_project(service_container, *, volume_count: int = 3, chapters_per_volume: int = 1) -> dict[str, object]:
    project_service = service_container["project_service"]
    bible_service = service_container["bible_service"]
    planner_service = service_container["planner_service"]
    file_repository = service_container["file_repository"]
    paths = service_container["paths"]

    manifest, _ = project_service.create_project(
        CreateProjectRequest(
            title="Continuity测试书",
            genre="都市异能",
            target_chapters=chapters_per_volume * volume_count,
            target_words=400_000,
        )
    )
    file_repository.write_json(
        paths.consultant_dossier_path(manifest.slug),
        {
            "dossier_id": "dossier_continuity",
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

    outline = planner_service.generate_volumes(
        manifest.project_id,
        volume_count_hint=volume_count,
        chapters_per_volume_hint=chapters_per_volume,
    )
    planner_service.confirm_master_outline(manifest.project_id)
    volume_ids: list[str] = []
    chapter_ids_by_volume: dict[str, list[str]] = {}
    for volume_ref in outline.volumes:
        volume_ids.append(volume_ref.volume_id)
        planner_service.confirm_volume(manifest.project_id, volume_ref.volume_id)
        chapters = planner_service.generate_chapters(manifest.project_id, volume_ref.volume_id)
        chapter_ids_by_volume[volume_ref.volume_id] = [chapter.chapter_id for chapter in chapters]
        for chapter in chapters:
            planner_service.confirm_chapter(manifest.project_id, chapter.chapter_id)

    return {
        "manifest": manifest,
        "paths": paths,
        "file_repository": file_repository,
        "planner_service": planner_service,
        "bible_service": bible_service,
        "volume_ids": volume_ids,
        "chapter_ids_by_volume": chapter_ids_by_volume,
    }


def _prepare_finalized_chapter(seed, chapter_service, draft_service, chapter_id: str):
    planner_service = seed["planner_service"]
    manifest = seed["manifest"]
    scenes = planner_service.generate_scenes(manifest.project_id, chapter_id, scene_count_hint=1)
    scene = scenes[0]
    planner_service.confirm_scene(manifest.project_id, scene.scene_id)
    draft = draft_service.generate(manifest.project_id, scene.scene_id, "outline_strict")
    draft_service.accept(manifest.project_id, draft.draft_id)
    chapter_service.assemble(manifest.project_id, chapter_id)
    return chapter_service.finalize(manifest.project_id, chapter_id)


def _prepare_finalized_volume(seed, chapter_service, draft_service, volume_service, volume_id: str):
    manifest = seed["manifest"]
    for chapter_id in seed["chapter_ids_by_volume"][volume_id]:
        _prepare_finalized_chapter(seed, chapter_service, draft_service, chapter_id)
    volume_service.assemble(manifest.project_id, volume_id)
    return volume_service.finalize(manifest.project_id, volume_id)


def test_continuity_report_flags_protagonist_absent_from_all_finalized_volumes(service_container) -> None:
    seed = _seed_multi_volume_project(service_container, volume_count=2, chapters_per_volume=1)
    draft_service, chapter_service, volume_service, book_service, continuity_service = _build_services(service_container)

    for volume_id in seed["volume_ids"]:
        _prepare_finalized_volume(seed, chapter_service, draft_service, volume_service, volume_id)

    manifest = seed["manifest"]
    seed["bible_service"].update_story_bible(manifest.project_id, {"protagonist_ids": ["char_missing_mc"]})
    book_service.assemble(manifest.project_id)

    report = continuity_service.run_for_book(manifest.project_id, "manual_recheck")
    assert report.overall_status == "blocked"
    assert any(issue.rule_id == "continuity.character.protagonist.absent_all" for issue in report.issues)


def test_continuity_report_flags_latest_volume_protagonist_absence_as_warning_only(service_container) -> None:
    seed = _seed_multi_volume_project(service_container, volume_count=2, chapters_per_volume=1)
    draft_service, chapter_service, volume_service, book_service, continuity_service = _build_services(service_container)

    for volume_id in seed["volume_ids"]:
        _prepare_finalized_volume(seed, chapter_service, draft_service, volume_service, volume_id)

    manifest = seed["manifest"]
    project_root = _project_root(seed)
    accepted_path = project_root / seed["paths"].relative_to_project(manifest.slug, seed["paths"].accepted_scenes_memory_path(manifest.slug))
    accepted = json.loads(accepted_path.read_text(encoding="utf-8"))
    last_volume_id = seed["volume_ids"][-1]
    accepted["items"] = [item for item in accepted["items"] if item["volume_id"] != last_volume_id]
    accepted_path.write_text(json.dumps(accepted, ensure_ascii=False, indent=2), encoding="utf-8")

    book_service.assemble(manifest.project_id)
    report = continuity_service.run_for_book(manifest.project_id, "manual_recheck")
    assert report.overall_status == "warning"
    assert any(issue.rule_id == "continuity.character.protagonist.absent_latest" for issue in report.issues)
    assert not any(issue.severity == "blocker" for issue in report.issues)


def test_book_finalize_is_blocked_by_continuity_preflight(service_container) -> None:
    seed = _seed_multi_volume_project(service_container, volume_count=2, chapters_per_volume=1)
    draft_service, chapter_service, volume_service, book_service, _ = _build_services(service_container)

    for volume_id in seed["volume_ids"]:
        _prepare_finalized_volume(seed, chapter_service, draft_service, volume_service, volume_id)

    manifest = seed["manifest"]
    seed["bible_service"].update_story_bible(manifest.project_id, {"protagonist_ids": ["char_missing_mc"]})
    book_service.assemble(manifest.project_id)

    with pytest.raises(ConflictError):
        book_service.finalize(manifest.project_id)
