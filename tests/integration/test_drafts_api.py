from __future__ import annotations

import os
from pathlib import Path

from fastapi.testclient import TestClient



def _project_root(slug: str) -> Path:
    return Path(os.environ["PROJECTS_ROOT"]) / slug



def test_scene_draft_generate_accept_reject_flow(client: TestClient, build_ready_scene_project) -> None:
    project = build_ready_scene_project(confirm_scene=True)

    generated = client.post(
        f"/api/projects/{project['project_id']}/drafts/scenes/{project['scene_id']}/generate",
        json={"mode": "outline_strict"},
    )
    assert generated.status_code == 201
    payload = generated.json()
    draft_id = payload["draft"]["draft_id"]
    assert payload["check_report"]["overall_status"] == "clean"

    latest_report = client.get(f"/api/projects/{project['project_id']}/drafts/{draft_id}/checks/latest")
    assert latest_report.status_code == 200
    assert latest_report.json()["report"]["draft_id"] == draft_id

    manifest = client.get(f"/api/projects/{project['project_id']}/drafts/scenes/{project['scene_id']}")
    assert manifest.status_code == 200
    assert manifest.json()["latest_draft_id"] == draft_id
    assert manifest.json()["accepted_draft_id"] is None

    rejected = client.post(f"/api/projects/{project['project_id']}/drafts/{draft_id}/reject")
    assert rejected.status_code == 200
    assert rejected.json()["draft"]["status"] == "rejected"

    generated_two = client.post(
        f"/api/projects/{project['project_id']}/drafts/scenes/{project['scene_id']}/generate",
        json={"mode": "momentum"},
    )
    assert generated_two.status_code == 201
    draft_two_id = generated_two.json()["draft"]["draft_id"]

    accepted = client.post(f"/api/projects/{project['project_id']}/drafts/{draft_two_id}/accept")
    assert accepted.status_code == 200
    assert accepted.json()["draft"]["status"] == "accepted"

    manifest_after = client.get(f"/api/projects/{project['project_id']}/drafts/scenes/{project['scene_id']}")
    assert manifest_after.status_code == 200
    assert manifest_after.json()["latest_draft_id"] == draft_two_id
    assert manifest_after.json()["accepted_draft_id"] == draft_two_id



def test_scene_draft_generate_returns_409_when_scene_not_ready(client: TestClient, build_ready_scene_project) -> None:
    project = build_ready_scene_project(confirm_scene=False)

    response = client.post(
        f"/api/projects/{project['project_id']}/drafts/scenes/{project['scene_id']}/generate",
        json={"mode": "outline_strict"},
    )
    assert response.status_code == 409



def test_accept_reject_on_non_draft_returns_409(client: TestClient, build_ready_scene_project) -> None:
    project = build_ready_scene_project(confirm_scene=True)

    generated = client.post(
        f"/api/projects/{project['project_id']}/drafts/scenes/{project['scene_id']}/generate",
        json={"mode": "outline_strict"},
    )
    draft_id = generated.json()["draft"]["draft_id"]

    accepted = client.post(f"/api/projects/{project['project_id']}/drafts/{draft_id}/accept")
    assert accepted.status_code == 200

    accept_again = client.post(f"/api/projects/{project['project_id']}/drafts/{draft_id}/accept")
    reject_after_accept = client.post(f"/api/projects/{project['project_id']}/drafts/{draft_id}/reject")
    assert accept_again.status_code == 409
    assert reject_after_accept.status_code == 409



def test_generate_uses_retrieved_memory_from_previous_accepted_scene(client: TestClient, build_ready_scene_project) -> None:
    project = build_ready_scene_project(confirm_scene=True)
    second_scene_id = project["scene_ids"][1]
    assert client.post(f"/api/projects/{project['project_id']}/plans/scenes/{second_scene_id}/confirm").status_code == 200

    first_generated = client.post(
        f"/api/projects/{project['project_id']}/drafts/scenes/{project['scene_id']}/generate",
        json={"mode": "outline_strict"},
    )
    assert first_generated.status_code == 201
    first_draft_id = first_generated.json()["draft"]["draft_id"]
    assert client.post(f"/api/projects/{project['project_id']}/drafts/{first_draft_id}/accept").status_code == 200

    second_generated = client.post(
        f"/api/projects/{project['project_id']}/drafts/scenes/{second_scene_id}/generate",
        json={"mode": "outline_strict"},
    )
    assert second_generated.status_code == 201
    retrieved = second_generated.json()["context_bundle"]["retrieved_memory"]
    assert retrieved["recent_scene_summaries"][0]["scene_id"] == project["scene_id"]



def test_recheck_endpoint_refreshes_draft_summary_fields(client: TestClient, build_ready_scene_project) -> None:
    project = build_ready_scene_project(confirm_scene=True)
    generated = client.post(
        f"/api/projects/{project['project_id']}/drafts/scenes/{project['scene_id']}/generate",
        json={"mode": "outline_strict"},
    )
    assert generated.status_code == 201
    draft = generated.json()["draft"]
    old_run_id = draft["latest_check_run_id"]

    draft_path = _project_root(project["slug"]) / draft["draft_path"]
    payload = __import__("json").loads(draft_path.read_text(encoding="utf-8"))
    payload["content_md"] = "空白文本"
    payload["summary"] = "空白摘要"
    payload["updated_at"] = "2026-03-12T12:00:00+00:00"
    draft_path.write_text(__import__("json").dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    rechecked = client.post(f"/api/projects/{project['project_id']}/drafts/{draft['draft_id']}/checks/recheck")
    assert rechecked.status_code == 200
    assert rechecked.json()["report"]["overall_status"] == "blocked"

    fetched = client.get(f"/api/projects/{project['project_id']}/drafts/{draft['draft_id']}")
    assert fetched.status_code == 200
    assert fetched.json()["draft"]["latest_check_run_id"] != old_run_id
    assert fetched.json()["draft"]["last_check_status"] == "blocked"
    assert fetched.json()["draft"]["last_check_blocker_count"] > 0



def test_blocker_draft_accept_returns_409(client: TestClient, build_ready_scene_project) -> None:
    project = build_ready_scene_project(confirm_scene=True)
    generated = client.post(
        f"/api/projects/{project['project_id']}/drafts/scenes/{project['scene_id']}/generate",
        json={"mode": "outline_strict"},
    )
    draft = generated.json()["draft"]

    draft_path = _project_root(project["slug"]) / draft["draft_path"]
    payload = __import__("json").loads(draft_path.read_text(encoding="utf-8"))
    payload["content_md"] = "空白文本"
    payload["summary"] = "空白摘要"
    payload["updated_at"] = "2026-03-12T12:00:00+00:00"
    draft_path.write_text(__import__("json").dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    response = client.post(f"/api/projects/{project['project_id']}/drafts/{draft['draft_id']}/accept")
    assert response.status_code == 409



def test_warning_only_draft_accept_returns_200(client: TestClient, build_ready_scene_project) -> None:
    project = build_ready_scene_project(confirm_scene=True)
    generated = client.post(
        f"/api/projects/{project['project_id']}/drafts/scenes/{project['scene_id']}/generate",
        json={"mode": "outline_strict"},
    )
    draft = generated.json()["draft"]

    draft_path = _project_root(project["slug"]) / draft["draft_path"]
    payload = __import__("json").loads(draft_path.read_text(encoding="utf-8"))
    payload["content_md"] = payload["content_md"].replace("阻碍：反派打压", "阻碍：")
    payload["updated_at"] = "2026-03-12T12:00:00+00:00"
    draft_path.write_text(__import__("json").dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    response = client.post(f"/api/projects/{project['project_id']}/drafts/{draft['draft_id']}/accept")
    assert response.status_code == 200
    assert response.json()["draft"]["status"] == "accepted"



def test_missing_report_on_accept_triggers_preflight_rerun(client: TestClient, build_ready_scene_project) -> None:
    project = build_ready_scene_project(confirm_scene=True)
    generated = client.post(
        f"/api/projects/{project['project_id']}/drafts/scenes/{project['scene_id']}/generate",
        json={"mode": "outline_strict"},
    )
    draft = generated.json()["draft"]
    old_run_id = draft["latest_check_run_id"]
    report_path = _project_root(project["slug"]) / draft["latest_check_report_path"]
    report_path.unlink()

    accepted = client.post(f"/api/projects/{project['project_id']}/drafts/{draft['draft_id']}/accept")
    assert accepted.status_code == 200
    assert accepted.json()["draft"]["latest_check_run_id"] != old_run_id



def test_scene_studio_page_is_available(client: TestClient) -> None:
    response = client.get("/studio/scene.html")
    assert response.status_code == 200

