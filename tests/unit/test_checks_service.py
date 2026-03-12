from __future__ import annotations

import pytest

from backend.app.domain.models.common import utc_now
from backend.app.services.exceptions import ConflictError


def _build_services(seeded):
    from backend.app.services.checks_service import ChecksService
    from backend.app.services.context_bundle_service import ContextBundleService
    from backend.app.services.memory_service import MemoryService
    from backend.app.services.retrieval_service import RetrievalService
    from backend.app.services.scene_draft_service import SceneDraftService

    paths = seeded["paths"]
    file_repository = seeded["file_repository"]
    sqlite_repository = seeded["sqlite_repository"]
    planner_service = seeded["planner_service"]
    bible_service = seeded["bible_service"]
    llm_gateway = seeded["llm_gateway"]

    retrieval_service = RetrievalService(paths, file_repository, sqlite_repository, planner_service)
    context_service = ContextBundleService(paths, file_repository, bible_service, planner_service, retrieval_service)
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
        llm_gateway,
    )
    return checks_service, draft_service



def test_run_for_draft_writes_report_and_draft_summary_fields(service_container) -> None:
    seeded = service_container["seed_project"](ready_scene=True, scene_count_hint=2)
    checks_service, draft_service = _build_services(seeded)
    manifest = seeded["manifest"]

    draft = draft_service.generate(manifest.project_id, seeded["scene_id"], mode="outline_strict")
    report = checks_service.get_latest_report(manifest.project_id, draft.draft_id)
    reloaded = draft_service.get_draft(manifest.project_id, draft.draft_id)

    assert report is not None
    assert report.draft_id == draft.draft_id
    assert report.overall_status == "clean"
    assert reloaded.latest_check_run_id == report.report_id
    assert reloaded.last_check_status == "clean"
    assert reloaded.last_check_blocker_count == 0
    assert reloaded.last_check_warning_count == 0
    assert reloaded.latest_check_report_path is not None
    assert reloaded.latest_check_report_path.endswith(f"checks/{draft.draft_id}.json")



def test_ensure_accept_allowed_reruns_when_draft_changes_and_blocks_on_blocker(service_container) -> None:
    seeded = service_container["seed_project"](ready_scene=True, scene_count_hint=2)
    checks_service, draft_service = _build_services(seeded)
    manifest = seeded["manifest"]
    paths = seeded["paths"]
    file_repository = seeded["file_repository"]

    draft = draft_service.generate(manifest.project_id, seeded["scene_id"], mode="outline_strict")
    draft_path = paths.project_root(manifest.slug) / draft.draft_path
    payload = file_repository.read_json(draft_path)
    payload["content_md"] = "空白文本"
    payload["summary"] = "空白摘要"
    payload["updated_at"] = utc_now().isoformat()
    file_repository.write_json(draft_path, payload)

    with pytest.raises(ConflictError):
        checks_service.ensure_accept_allowed(manifest.project_id, draft.draft_id)

    report = checks_service.get_latest_report(manifest.project_id, draft.draft_id)
    assert report is not None
    assert report.overall_status == "blocked"
    assert report.blocker_count > 0



def test_warning_report_does_not_block_accept(service_container) -> None:
    seeded = service_container["seed_project"](ready_scene=True, scene_count_hint=2)
    checks_service, draft_service = _build_services(seeded)
    manifest = seeded["manifest"]
    paths = seeded["paths"]
    file_repository = seeded["file_repository"]

    draft = draft_service.generate(manifest.project_id, seeded["scene_id"], mode="outline_strict")
    draft_path = paths.project_root(manifest.slug) / draft.draft_path
    payload = file_repository.read_json(draft_path)
    obstacle = seeded["scenes"][0].obstacle
    payload["content_md"] = payload["content_md"].replace(f"阻碍：{obstacle}", "阻碍：")
    payload["content_md"] = payload["content_md"].replace(f"先遭遇“{obstacle}”", "先遭遇“”")
    payload["summary"] = payload["summary"].replace(obstacle, "")
    payload["updated_at"] = utc_now().isoformat()
    file_repository.write_json(draft_path, payload)

    report = checks_service.ensure_accept_allowed(manifest.project_id, draft.draft_id)
    assert report.overall_status == "warning"
    assert report.blocker_count == 0
    assert report.warning_count > 0



def test_error_report_blocks_accept(service_container, monkeypatch: pytest.MonkeyPatch) -> None:
    seeded = service_container["seed_project"](ready_scene=True, scene_count_hint=2)
    checks_service, draft_service = _build_services(seeded)
    manifest = seeded["manifest"]

    draft = draft_service.generate(manifest.project_id, seeded["scene_id"], mode="outline_strict")

    def _boom(_input_ctx):
        raise RuntimeError("boom")

    monkeypatch.setattr(checks_service.evaluators[0], "evaluate", _boom)
    report = checks_service.run_for_draft(manifest.project_id, draft.draft_id, trigger="manual_recheck")
    assert report.overall_status == "error"

    with pytest.raises(ConflictError):
        checks_service.ensure_accept_allowed(manifest.project_id, draft.draft_id)


