from __future__ import annotations

from fastapi.testclient import TestClient


def test_scene_draft_generate_accept_reject_flow(client: TestClient, build_ready_scene_project) -> None:
    project = build_ready_scene_project(confirm_scene=True)

    generated = client.post(
        f"/api/projects/{project['project_id']}/drafts/scenes/{project['scene_id']}/generate",
        json={"mode": "outline_strict"},
    )
    assert generated.status_code == 201
    draft_id = generated.json()["draft"]["draft_id"]

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


def test_scene_studio_page_is_available(client: TestClient) -> None:
    response = client.get("/studio/scene.html")
    assert response.status_code == 200
