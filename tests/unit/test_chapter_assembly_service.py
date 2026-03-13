from __future__ import annotations

import json
from pathlib import Path

import pytest


def _build_services(seeded):
    from backend.app.services.chapter_assembly_service import ChapterAssemblyService
    from backend.app.services.chapter_checks_service import ChapterChecksService
    from backend.app.services.checks_service import ChecksService
    from backend.app.services.context_bundle_service import ContextBundleService
    from backend.app.services.memory_service import MemoryService
    from backend.app.services.retrieval_service import RetrievalService
    from backend.app.services.scene_draft_service import SceneDraftService
    from backend.app.services.style_service import StyleService
    from backend.app.services.voice_constraint_builder import VoiceConstraintBuilder

    paths = seeded["paths"]
    file_repository = seeded["file_repository"]
    sqlite_repository = seeded["sqlite_repository"]
    planner_service = seeded["planner_service"]
    bible_service = seeded["bible_service"]
    llm_gateway = seeded["llm_gateway"]

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
    return draft_service, chapter_service, chapter_checks_service, memory_service


def _project_root(seeded) -> Path:
    return seeded["paths"].project_root(seeded["manifest"].slug)


def _accept_scene_draft(draft_service, project_id: str, scene_id: str, mode: str = "outline_strict"):
    draft = draft_service.generate(project_id, scene_id, mode=mode)
    return draft_service.accept(project_id, draft.draft_id)


def test_chapter_assemble_trims_content_and_freezes_snapshot_and_version_rules(service_container) -> None:
    seeded = service_container["seed_project"](ready_scene=True, scene_count_hint=2)
    manifest = seeded["manifest"]
    seeded["planner_service"].confirm_scene(manifest.project_id, seeded["scenes"][1].scene_id)
    draft_service, chapter_service, _, _ = _build_services(seeded)

    accepted_one = _accept_scene_draft(draft_service, manifest.project_id, seeded["scenes"][0].scene_id)
    accepted_two = _accept_scene_draft(draft_service, manifest.project_id, seeded["scenes"][1].scene_id, mode="momentum")

    root = _project_root(seeded)
    first_path = root / accepted_one.draft_path
    second_path = root / accepted_two.draft_path
    first_payload = json.loads(first_path.read_text(encoding="utf-8"))
    second_payload = json.loads(second_path.read_text(encoding="utf-8"))
    first_payload["content_md"] = "  第一段内容  \n"
    second_payload["content_md"] = "\n 第二段内容 "
    first_path.write_text(json.dumps(first_payload, ensure_ascii=False, indent=2), encoding="utf-8")
    second_path.write_text(json.dumps(second_payload, ensure_ascii=False, indent=2), encoding="utf-8")

    assembled = chapter_service.assemble(manifest.project_id, seeded["chapter_id"])
    assert assembled.version == 1
    assert assembled.status == "assembled"
    assert assembled.content_md == "第一段内容\n\n第二段内容"
    assert assembled.source_versions.accepted_draft_ids[seeded["scenes"][0].scene_id] == accepted_one.draft_id
    assert assembled.source_versions.accepted_draft_ids[seeded["scenes"][1].scene_id] == accepted_two.draft_id
    frozen_scene_versions = dict(assembled.source_versions.scene_versions)
    frozen_accepted_ids = dict(assembled.source_versions.accepted_draft_ids)

    report = chapter_service.recheck(manifest.project_id, seeded["chapter_id"])
    assert report.overall_status == "warning"
    assert report.warning_count > 0
    reloaded = chapter_service.get_assembled(manifest.project_id, seeded["chapter_id"])
    assert reloaded.version == 1
    assert reloaded.source_versions.scene_versions == frozen_scene_versions
    assert reloaded.source_versions.accepted_draft_ids == frozen_accepted_ids

    finalized = chapter_service.finalize(manifest.project_id, seeded["chapter_id"])
    assert finalized.status == "finalized"
    assert finalized.version == 1
    assert finalized.finalized_from_assembly_version == 1
    assert finalized.content_md == "第一段内容\n\n第二段内容"


def test_chapter_assemble_rejects_duplicate_accepted_scene(service_container) -> None:
    from backend.app.services.exceptions import ConflictError

    seeded = service_container["seed_project"](ready_scene=True, scene_count_hint=2)
    manifest = seeded["manifest"]
    seeded["planner_service"].confirm_scene(manifest.project_id, seeded["scenes"][1].scene_id)
    draft_service, chapter_service, _, _ = _build_services(seeded)

    accepted_one = _accept_scene_draft(draft_service, manifest.project_id, seeded["scenes"][0].scene_id)
    _accept_scene_draft(draft_service, manifest.project_id, seeded["scenes"][1].scene_id)
    duplicate = draft_service.generate(manifest.project_id, seeded["scenes"][0].scene_id, mode="momentum")

    duplicate_path = _project_root(seeded) / duplicate.draft_path
    duplicate_payload = json.loads(duplicate_path.read_text(encoding="utf-8"))
    duplicate_payload["status"] = "accepted"
    duplicate_payload["accepted_at"] = "2026-03-13T00:00:00+00:00"
    duplicate_path.write_text(json.dumps(duplicate_payload, ensure_ascii=False, indent=2), encoding="utf-8")

    accepted_path = _project_root(seeded) / accepted_one.draft_path
    accepted_payload = json.loads(accepted_path.read_text(encoding="utf-8"))
    accepted_payload["status"] = "accepted"
    accepted_path.write_text(json.dumps(accepted_payload, ensure_ascii=False, indent=2), encoding="utf-8")

    with pytest.raises(ConflictError):
        chapter_service.assemble(manifest.project_id, seeded["chapter_id"])


def test_chapter_stale_rules_finalize_idempotency_and_memory_persistence(service_container) -> None:
    from backend.app.services.exceptions import ConflictError

    seeded = service_container["seed_project"](ready_scene=True, scene_count_hint=2)
    manifest = seeded["manifest"]
    planner_service = seeded["planner_service"]
    planner_service.confirm_scene(manifest.project_id, seeded["scenes"][1].scene_id)
    draft_service, chapter_service, _, memory_service = _build_services(seeded)

    _accept_scene_draft(draft_service, manifest.project_id, seeded["scenes"][0].scene_id)
    _accept_scene_draft(draft_service, manifest.project_id, seeded["scenes"][1].scene_id)

    assembled = chapter_service.assemble(manifest.project_id, seeded["chapter_id"])
    finalized = chapter_service.finalize(manifest.project_id, seeded["chapter_id"])
    finalized_again = chapter_service.finalize(manifest.project_id, seeded["chapter_id"])
    assert finalized.status == "finalized"
    assert finalized_again.status == "finalized"
    assert finalized_again.version == assembled.version

    slug = manifest.slug
    chapter_summary_before = memory_service.read_chapter_summaries(slug, manifest.project_id)
    summary_item_before = next(item for item in chapter_summary_before.items if item.chapter_id == seeded["chapter_id"])
    assert summary_item_before.summary == finalized.summary

    extra_draft = draft_service.generate(manifest.project_id, seeded["scenes"][0].scene_id, mode="outline_strict")
    draft_service.reject(manifest.project_id, extra_draft.draft_id)
    after_reject = chapter_service.get_assembled(manifest.project_id, seeded["chapter_id"])
    assert after_reject.status == "finalized"

    accepted_replacement = draft_service.generate(manifest.project_id, seeded["scenes"][0].scene_id, mode="momentum")
    draft_service.accept(manifest.project_id, accepted_replacement.draft_id)
    stale = chapter_service.get_assembled(manifest.project_id, seeded["chapter_id"])
    assert stale.status == "stale"

    report = chapter_service.recheck(manifest.project_id, seeded["chapter_id"])
    assert report.overall_status == "blocked"
    still_stale = chapter_service.get_assembled(manifest.project_id, seeded["chapter_id"])
    assert still_stale.status == "stale"

    with pytest.raises(ConflictError):
        chapter_service.finalize(manifest.project_id, seeded["chapter_id"])

    chapter_summary_after = memory_service.read_chapter_summaries(slug, manifest.project_id)
    summary_item_after = next(item for item in chapter_summary_after.items if item.chapter_id == seeded["chapter_id"])
    assert summary_item_after.summary == summary_item_before.summary
