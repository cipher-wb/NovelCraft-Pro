from __future__ import annotations

import json
import os
from pathlib import Path

from fastapi.testclient import TestClient


def _project_root(slug: str) -> Path:
    return Path(os.environ["PROJECTS_ROOT"]) / slug


def _generate_and_accept(client: TestClient, project_id: str, scene_id: str, *, mode: str = "outline_strict") -> dict:
    generated = client.post(
        f"/api/projects/{project_id}/drafts/scenes/{scene_id}/generate",
        json={"mode": mode},
    )
    assert generated.status_code == 201
    draft = generated.json()["draft"]
    accepted = client.post(f"/api/projects/{project_id}/drafts/{draft['draft_id']}/accept")
    assert accepted.status_code == 200
    return accepted.json()["draft"]


def test_chapter_api_assemble_recheck_finalize_and_memory_flow(client: TestClient, build_ready_scene_project) -> None:
    project = build_ready_scene_project(confirm_scene=True)
    for index, scene_id in enumerate(project["scene_ids"]):
        if index > 0:
            assert client.post(f"/api/projects/{project['project_id']}/plans/scenes/{scene_id}/confirm").status_code == 200
        _generate_and_accept(
            client,
            project["project_id"],
            scene_id,
            mode="momentum" if index % 2 else "outline_strict",
        )

    assembled = client.post(f"/api/projects/{project['project_id']}/chapters/{project['chapter_id']}/assemble")
    assert assembled.status_code == 200
    assembled_payload = assembled.json()
    assert assembled_payload["assembled"]["status"] == "assembled"
    assert assembled_payload["check_report"]["overall_status"] == "clean"

    fetched = client.get(f"/api/projects/{project['project_id']}/chapters/{project['chapter_id']}/assembled")
    assert fetched.status_code == 200
    assert fetched.json()["status"] == "assembled"

    rechecked = client.post(f"/api/projects/{project['project_id']}/chapters/{project['chapter_id']}/checks/recheck")
    assert rechecked.status_code == 200
    assert rechecked.json()["report"]["overall_status"] == "clean"

    finalized = client.post(f"/api/projects/{project['project_id']}/chapters/{project['chapter_id']}/finalize")
    assert finalized.status_code == 200
    assert finalized.json()["assembled"]["status"] == "finalized"

    memory_path = _project_root(project["slug"]) / "memory" / "chapter_summaries.json"
    memory_payload = json.loads(memory_path.read_text(encoding="utf-8"))
    item = next(entry for entry in memory_payload["items"] if entry["chapter_id"] == project["chapter_id"])
    assert item["summary"] == finalized.json()["assembled"]["summary"]


def test_chapter_api_requires_all_scenes_have_unique_active_accepted_drafts(client: TestClient, build_ready_scene_project) -> None:
    project = build_ready_scene_project(confirm_scene=True)
    second_scene_id = project["scene_ids"][1]
    assert client.post(f"/api/projects/{project['project_id']}/plans/scenes/{second_scene_id}/confirm").status_code == 200

    _generate_and_accept(client, project["project_id"], project["scene_id"])
    missing = client.post(f"/api/projects/{project['project_id']}/chapters/{project['chapter_id']}/assemble")
    assert missing.status_code == 409

    first_again = client.post(
        f"/api/projects/{project['project_id']}/drafts/scenes/{project['scene_id']}/generate",
        json={"mode": "momentum"},
    )
    assert first_again.status_code == 201
    duplicate_draft = first_again.json()["draft"]
    duplicate_path = _project_root(project["slug"]) / duplicate_draft["draft_path"]
    duplicate_payload = json.loads(duplicate_path.read_text(encoding="utf-8"))
    duplicate_payload["status"] = "accepted"
    duplicate_payload["accepted_at"] = "2026-03-13T00:00:00+00:00"
    duplicate_path.write_text(json.dumps(duplicate_payload, ensure_ascii=False, indent=2), encoding="utf-8")

    _generate_and_accept(client, project["project_id"], second_scene_id)
    duplicate = client.post(f"/api/projects/{project['project_id']}/chapters/{project['chapter_id']}/assemble")
    assert duplicate.status_code == 409


def test_chapter_api_stale_only_on_active_accepted_changes_and_finalize_rules(client: TestClient, build_ready_scene_project) -> None:
    project = build_ready_scene_project(confirm_scene=True)
    second_scene_id = project["scene_ids"][1]
    for scene_id in project["scene_ids"][1:]:
        assert client.post(f"/api/projects/{project['project_id']}/plans/scenes/{scene_id}/confirm").status_code == 200

    for index, scene_id in enumerate(project["scene_ids"]):
        _generate_and_accept(
            client,
            project["project_id"],
            scene_id,
            mode="momentum" if index % 2 else "outline_strict",
        )
    assert client.post(f"/api/projects/{project['project_id']}/chapters/{project['chapter_id']}/assemble").status_code == 200
    assert client.post(f"/api/projects/{project['project_id']}/chapters/{project['chapter_id']}/finalize").status_code == 200

    extra = client.post(
        f"/api/projects/{project['project_id']}/drafts/scenes/{project['scene_id']}/generate",
        json={"mode": "outline_strict"},
    )
    assert extra.status_code == 201
    extra_draft_id = extra.json()["draft"]["draft_id"]
    assert client.post(f"/api/projects/{project['project_id']}/drafts/{extra_draft_id}/reject").status_code == 200

    still_finalized = client.get(f"/api/projects/{project['project_id']}/chapters/{project['chapter_id']}/assembled")
    assert still_finalized.status_code == 200
    assert still_finalized.json()["status"] == "finalized"

    replacement = client.post(
        f"/api/projects/{project['project_id']}/drafts/scenes/{project['scene_id']}/generate",
        json={"mode": "momentum"},
    )
    assert replacement.status_code == 201
    replacement_id = replacement.json()["draft"]["draft_id"]
    assert client.post(f"/api/projects/{project['project_id']}/drafts/{replacement_id}/accept").status_code == 200

    stale = client.get(f"/api/projects/{project['project_id']}/chapters/{project['chapter_id']}/assembled")
    assert stale.status_code == 200
    assert stale.json()["status"] == "stale"

    rechecked = client.post(f"/api/projects/{project['project_id']}/chapters/{project['chapter_id']}/checks/recheck")
    assert rechecked.status_code == 200
    assert client.get(f"/api/projects/{project['project_id']}/chapters/{project['chapter_id']}/assembled").json()["status"] == "stale"

    finalize = client.post(f"/api/projects/{project['project_id']}/chapters/{project['chapter_id']}/finalize")
    assert finalize.status_code == 409


def test_chapter_studio_page_is_available(client: TestClient) -> None:
    response = client.get("/studio/chapter.html")
    assert response.status_code == 200
    assert "Assemble Chapter" in response.text
