from __future__ import annotations

import json

import pytest


def _build_services(seeded):
    from backend.app.services.checks_service import ChecksService
    from backend.app.services.context_bundle_service import ContextBundleService
    from backend.app.services.memory_service import MemoryService
    from backend.app.services.repair_service import RepairService
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
    repair_service = RepairService(
        paths,
        file_repository,
        sqlite_repository,
        planner_service,
        draft_service,
        context_service,
        checks_service,
        style_service,
        llm_gateway,
    )
    return draft_service, checks_service, repair_service


def _rewrite_draft(file_repository, paths, slug: str, draft, *, content_md: str | None = None, summary: str | None = None) -> None:
    payload = draft.model_dump(mode="json")
    if content_md is not None:
        payload["content_md"] = content_md
    if summary is not None:
        payload["summary"] = summary
    payload["updated_at"] = "2026-03-12T12:00:00+00:00"
    file_repository.write_json(paths.project_root(slug) / draft.draft_path, payload)


def test_repair_rechecks_stale_generate_auto_report_and_creates_repaired_draft(service_container) -> None:
    seeded = service_container["seed_project"](ready_scene=True, scene_count_hint=2)
    manifest = seeded["manifest"]
    paths = seeded["paths"]
    file_repository = seeded["file_repository"]
    draft_service, checks_service, repair_service = _build_services(seeded)

    source = draft_service.generate(manifest.project_id, seeded["scene_id"], mode="outline_strict")
    _rewrite_draft(
        file_repository,
        paths,
        manifest.slug,
        source,
        content_md="空白文本",
        summary="空白摘要",
    )

    repaired = repair_service.repair_draft(manifest.project_id, source.draft_id)
    source_after = draft_service.get_draft(manifest.project_id, source.draft_id)
    manifest_after = draft_service.get_scene_manifest(manifest.project_id, seeded["scene_id"])
    repaired_report = checks_service.get_latest_report(manifest.project_id, repaired.draft_id)

    assert repaired.operation == "repair"
    assert repaired.repair_metadata is not None
    assert repaired.repair_metadata.source_draft_id == source.draft_id
    assert repaired.supersedes_draft_id == source.draft_id
    assert source_after.status == "superseded"
    assert manifest_after.latest_draft_id == repaired.draft_id
    assert manifest_after.last_draft_no == source.draft_no + 1
    assert repaired_report is not None
    assert repaired_report.trigger == "repair_auto"
    assert repaired.latest_check_report_path != source.latest_check_report_path


def test_repair_rejects_clean_and_error_reports(service_container, monkeypatch: pytest.MonkeyPatch) -> None:
    from backend.app.domain.models.issues import SceneDraftCheckReport
    from backend.app.services.exceptions import ConflictError

    seeded = service_container["seed_project"](ready_scene=True, scene_count_hint=2)
    manifest = seeded["manifest"]
    draft_service, checks_service, repair_service = _build_services(seeded)

    clean_source = draft_service.generate(manifest.project_id, seeded["scene_id"], mode="outline_strict")
    with pytest.raises(ConflictError):
        repair_service.repair_draft(manifest.project_id, clean_source.draft_id)

    warning_source = draft_service.generate(manifest.project_id, seeded["scene_id"], mode="momentum")
    stale_report = checks_service.run_for_draft(manifest.project_id, warning_source.draft_id, trigger="manual_recheck")
    error_report = SceneDraftCheckReport.model_validate(
        {
            **stale_report.model_dump(mode="json"),
            "report_id": "check_error_case",
            "overall_status": "error",
            "blocker_count": 0,
            "warning_count": 0,
            "issues": [],
            "rule_summaries": [],
        }
    )
    monkeypatch.setattr(repair_service, "_get_latest_usable_report", lambda *_args, **_kwargs: error_report)
    with pytest.raises(ConflictError):
        repair_service.repair_draft(manifest.project_id, warning_source.draft_id)


def test_repair_failure_does_not_change_manifest_or_source_status(service_container, monkeypatch: pytest.MonkeyPatch) -> None:
    from backend.app.services.exceptions import ConflictError

    seeded = service_container["seed_project"](ready_scene=True, scene_count_hint=2)
    manifest = seeded["manifest"]
    paths = seeded["paths"]
    file_repository = seeded["file_repository"]
    draft_service, checks_service, repair_service = _build_services(seeded)

    source = draft_service.generate(manifest.project_id, seeded["scene_id"], mode="outline_strict")
    _rewrite_draft(
        file_repository,
        paths,
        manifest.slug,
        source,
        content_md="空白文本",
        summary="空白摘要",
    )
    before_manifest = json.loads(json.dumps(draft_service.get_scene_manifest(manifest.project_id, seeded["scene_id"]).model_dump(mode="json")))

    original = checks_service.run_for_draft

    def _explode(*args, **kwargs):
        if kwargs.get("trigger") == "repair_auto":
            raise RuntimeError("boom")
        return original(*args, **kwargs)

    monkeypatch.setattr(checks_service, "run_for_draft", _explode)

    with pytest.raises(ConflictError):
        repair_service.repair_draft(manifest.project_id, source.draft_id)

    after_source = draft_service.get_draft(manifest.project_id, source.draft_id)
    after_manifest = draft_service.get_scene_manifest(manifest.project_id, seeded["scene_id"]).model_dump(mode="json")
    assert after_source.status == "draft"
    assert after_manifest == before_manifest


def test_repair_sanitizes_with_style_without_breaking_key_blocker_phrases(service_container) -> None:
    seeded = service_container["seed_project"](ready_scene=True, scene_count_hint=2)
    manifest = seeded["manifest"]
    paths = seeded["paths"]
    file_repository = seeded["file_repository"]
    draft_service, _checks_service, repair_service = _build_services(seeded)

    file_repository.write_json(
        paths.voice_profile_path(manifest.slug),
        {
            "project_id": manifest.project_id,
            "version": 1,
            "updated_at": "2026-03-13T00:00:00Z",
            "enabled": True,
            "profile_name": "风格测试",
            "global_constraints": {
                "sentence_rhythm": {
                    "baseline": "short",
                    "soft_max_sentence_chars": 30,
                    "burst_short_lines": True,
                },
                "paragraph_rhythm": {
                    "preferred_min_sentences": 1,
                    "preferred_max_sentences": 2,
                    "soft_max_sentences": 3,
                },
                "banned_phrases": ["空气都安静了"],
                "narrative_habits": {
                    "narration_person": "third_limited",
                    "exposition_density": "low",
                    "inner_monologue_density": "low",
                    "dialogue_tag_style": "simple",
                },
                "payoff_style": {
                    "intensity": "direct",
                    "prefer_action_before_reaction": True,
                    "prefer_concrete_gain": True,
                    "avoid_empty_hype": True,
                },
            },
            "character_voice_profiles": [],
            "notes": "",
        },
    )

    source = draft_service.generate(manifest.project_id, seeded["scene_id"], mode="outline_strict")
    _rewrite_draft(
        file_repository,
        paths,
        manifest.slug,
        source,
        content_md="空白文本。空气都安静了。",
        summary="空白摘要。空气都安静了。",
    )

    repaired = repair_service.repair_draft(manifest.project_id, source.draft_id)
    scene = seeded["planner_service"].get_scene(manifest.project_id, seeded["scene_id"])
    assert "空气都安静了" not in repaired.content_md
    assert scene.goal in repaired.content_md
    assert scene.turning_point in repaired.content_md
    assert scene.outcome in repaired.content_md
