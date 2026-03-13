from __future__ import annotations

import json
from pathlib import Path

import pytest

from backend.app.schemas.project import CreateProjectRequest


def _build_services(service_container):
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
    return draft_service, chapter_service, volume_service, volume_checks_service, memory_service


def _project_root(seed) -> Path:
    return seed["paths"].project_root(seed["manifest"].slug)


def _seed_small_project(service_container, *, volume_count: int = 1, chapters_per_volume: int = 2) -> dict[str, object]:
    project_service = service_container["project_service"]
    consultant_service = service_container["consultant_service"]
    bible_service = service_container["bible_service"]
    planner_service = service_container["planner_service"]
    file_repository = service_container["file_repository"]
    paths = service_container["paths"]

    manifest, _ = project_service.create_project(
        CreateProjectRequest(
            title="Volume测试书",
            genre="都市异能",
            target_chapters=chapters_per_volume * volume_count,
            target_words=200_000,
        )
    )
    file_repository.write_json(
        paths.consultant_dossier_path(manifest.slug),
        {
            "dossier_id": "dossier_volume",
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
    for volume_ref in outline.volumes:
        planner_service.confirm_volume(manifest.project_id, volume_ref.volume_id)
        chapters = planner_service.generate_chapters(manifest.project_id, volume_ref.volume_id)
        for chapter in chapters:
            planner_service.confirm_chapter(manifest.project_id, chapter.chapter_id)

    return {
        "manifest": manifest,
        "paths": paths,
        "file_repository": file_repository,
        "planner_service": planner_service,
        "volume_id": outline.volumes[0].volume_id,
    }


def _prepare_finalized_chapter(seed, chapter_service, draft_service, chapter_id: str, *, scene_count_hint: int = 2):
    planner_service = seed["planner_service"]
    manifest = seed["manifest"]
    chapter = planner_service.get_chapter(manifest.project_id, chapter_id)
    scenes = planner_service.generate_scenes(manifest.project_id, chapter.chapter_id, scene_count_hint=scene_count_hint)
    for index, scene in enumerate(scenes):
        planner_service.confirm_scene(manifest.project_id, scene.scene_id)
        draft = draft_service.generate(manifest.project_id, scene.scene_id, "momentum" if index % 2 else "outline_strict")
        draft_service.accept(manifest.project_id, draft.draft_id)
    chapter_service.assemble(manifest.project_id, chapter.chapter_id)
    return chapter_service.finalize(manifest.project_id, chapter.chapter_id)


def test_volume_assemble_uses_finalized_chapters_and_freezes_snapshot_version_rules(service_container) -> None:
    seed = _seed_small_project(service_container, chapters_per_volume=2)
    manifest = seed["manifest"]
    planner_service = seed["planner_service"]
    draft_service, chapter_service, volume_service, _, _ = _build_services(service_container)

    chapters = planner_service.list_chapters(manifest.project_id, seed["volume_id"])[:2]
    first_finalized = _prepare_finalized_chapter(seed, chapter_service, draft_service, chapters[0].chapter_id)
    second_finalized = _prepare_finalized_chapter(seed, chapter_service, draft_service, chapters[1].chapter_id)

    first_path = _project_root(seed) / service_container["paths"].relative_to_project(
        manifest.slug,
        service_container["paths"].chapter_assembled_path(manifest.slug, chapters[0].chapter_id),
    )
    second_path = _project_root(seed) / service_container["paths"].relative_to_project(
        manifest.slug,
        service_container["paths"].chapter_assembled_path(manifest.slug, chapters[1].chapter_id),
    )
    first_payload = json.loads(first_path.read_text(encoding="utf-8"))
    second_payload = json.loads(second_path.read_text(encoding="utf-8"))
    first_payload["content_md"] = "  第一章正文  \n"
    second_payload["content_md"] = "\n 第二章正文 "
    first_path.write_text(json.dumps(first_payload, ensure_ascii=False, indent=2), encoding="utf-8")
    second_path.write_text(json.dumps(second_payload, ensure_ascii=False, indent=2), encoding="utf-8")

    assembled = volume_service.assemble(manifest.project_id, seed["volume_id"])
    assert assembled.version == 1
    assert assembled.status == "assembled"
    assert assembled.content_md == "第一章正文\n\n第二章正文"
    assert assembled.planned_chapter_order == [chapters[0].chapter_id, chapters[1].chapter_id]
    assert [item.chapter_id for item in assembled.chapter_order] == [chapters[0].chapter_id, chapters[1].chapter_id]
    assert assembled.chapter_order[0].assembled_version == first_finalized.version
    assert assembled.chapter_order[1].assembled_version == second_finalized.version
    frozen_planned = list(assembled.planned_chapter_order)
    frozen_order = [item.model_dump(mode="python") for item in assembled.chapter_order]
    frozen_content = assembled.content_md
    frozen_summary = assembled.summary
    frozen_hook = assembled.hook
    frozen_stats = assembled.progress_stats.model_dump(mode="python")

    report = volume_service.recheck(manifest.project_id, seed["volume_id"])
    assert report.overall_status == "clean"
    reloaded = volume_service.get_assembled(manifest.project_id, seed["volume_id"])
    assert reloaded.version == 1
    assert reloaded.planned_chapter_order == frozen_planned
    assert [item.model_dump(mode="python") for item in reloaded.chapter_order] == frozen_order
    assert reloaded.content_md == frozen_content
    assert reloaded.summary == frozen_summary
    assert reloaded.hook == frozen_hook
    assert reloaded.progress_stats.model_dump(mode="python") == frozen_stats

    finalized = volume_service.finalize(manifest.project_id, seed["volume_id"])
    assert finalized.status == "finalized"
    assert finalized.version == 1
    assert finalized.finalized_from_assembly_version == 1
    assert finalized.content_md == frozen_content


def test_volume_partial_assemble_blocks_finalize_and_memory_updates_only_on_finalize(service_container) -> None:
    from backend.app.services.exceptions import ConflictError

    seed = _seed_small_project(service_container, chapters_per_volume=2)
    manifest = seed["manifest"]
    planner_service = seed["planner_service"]
    draft_service, chapter_service, volume_service, _, memory_service = _build_services(service_container)

    chapters = planner_service.list_chapters(manifest.project_id, seed["volume_id"])[:2]
    _prepare_finalized_chapter(seed, chapter_service, draft_service, chapters[0].chapter_id)

    assembled = volume_service.assemble(manifest.project_id, seed["volume_id"])
    assert assembled.status == "assembled"

    report = volume_service.get_latest_report(manifest.project_id, seed["volume_id"])
    assert report is not None
    assert report.overall_status == "blocked"
    assert any(issue.rule_id == "volume.chapter.finalized.missing" for issue in report.issues)

    memory_before = memory_service.read_volume_summaries(manifest.slug, manifest.project_id)
    assert memory_before.items == []

    with pytest.raises(ConflictError):
        volume_service.finalize(manifest.project_id, seed["volume_id"])

    memory_after = memory_service.read_volume_summaries(manifest.slug, manifest.project_id)
    assert memory_after.items == []


def test_volume_stale_only_from_current_volume_and_get_refresh_is_read_only(service_container) -> None:
    from backend.app.services.exceptions import ConflictError

    seed = _seed_small_project(service_container, volume_count=2, chapters_per_volume=2)
    manifest = seed["manifest"]
    planner_service = seed["planner_service"]
    draft_service, chapter_service, volume_service, _, memory_service = _build_services(service_container)

    volumes = planner_service.list_volumes(manifest.project_id)
    primary_volume = volumes[0]
    secondary_volume = volumes[1]
    primary_chapters = planner_service.list_chapters(manifest.project_id, primary_volume.volume_id)[:2]
    secondary_chapters = planner_service.list_chapters(manifest.project_id, secondary_volume.volume_id)[:2]

    _prepare_finalized_chapter(seed, chapter_service, draft_service, primary_chapters[0].chapter_id)
    _prepare_finalized_chapter(seed, chapter_service, draft_service, primary_chapters[1].chapter_id)

    assembled = volume_service.assemble(manifest.project_id, primary_volume.volume_id)
    finalized = volume_service.finalize(manifest.project_id, primary_volume.volume_id)
    memory_before = memory_service.read_volume_summaries(manifest.slug, manifest.project_id)
    item_before = next(item for item in memory_before.items if item.volume_id == primary_volume.volume_id)

    planner_service.update_chapter(manifest.project_id, secondary_chapters[0].chapter_id, {"summary": "other volume changed"})
    still_finalized = volume_service.get_assembled(manifest.project_id, primary_volume.volume_id)
    assert still_finalized.status == "finalized"
    assert still_finalized.version == finalized.version

    updated_scene = draft_service.generate(
        manifest.project_id,
        planner_service.list_scenes(manifest.project_id, primary_chapters[0].chapter_id)[0].scene_id,
        "outline_strict",
    )
    draft_service.reject(manifest.project_id, updated_scene.draft_id)
    after_reject = volume_service.get_assembled(manifest.project_id, primary_volume.volume_id)
    assert after_reject.status == "finalized"

    replacement = draft_service.generate(manifest.project_id, planner_service.list_scenes(manifest.project_id, primary_chapters[0].chapter_id)[0].scene_id, mode="momentum")
    draft_service.accept(manifest.project_id, replacement.draft_id)
    chapter_service.get_assembled(manifest.project_id, primary_chapters[0].chapter_id)

    stale = volume_service.get_assembled(manifest.project_id, primary_volume.volume_id)
    assert stale.status == "stale"
    assert stale.version == assembled.version
    assert stale.content_md == assembled.content_md
    assert stale.summary == assembled.summary
    assert stale.hook == assembled.hook
    assert stale.progress_stats.model_dump(mode="python") == assembled.progress_stats.model_dump(mode="python")

    rechecked = volume_service.recheck(manifest.project_id, primary_volume.volume_id)
    assert rechecked.overall_status == "blocked"
    still_stale = volume_service.get_assembled(manifest.project_id, primary_volume.volume_id)
    assert still_stale.status == "stale"

    with pytest.raises(ConflictError):
        volume_service.finalize(manifest.project_id, primary_volume.volume_id)

    memory_after = memory_service.read_volume_summaries(manifest.slug, manifest.project_id)
    item_after = next(item for item in memory_after.items if item.volume_id == primary_volume.volume_id)
    assert item_after.summary == item_before.summary
