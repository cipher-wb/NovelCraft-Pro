from __future__ import annotations

from fastapi.testclient import TestClient



def _prepare_ready_bible(client: TestClient, create_finalized_project) -> dict[str, str]:
    project = create_finalized_project()
    create = client.post(f"/api/projects/{project['project_id']}/bible/from-consultant")
    assert create.status_code == 201
    assert client.post(f"/api/projects/{project['project_id']}/characters/confirm").status_code == 200
    assert client.post(f"/api/projects/{project['project_id']}/bible/world/confirm").status_code == 200
    assert client.post(f"/api/projects/{project['project_id']}/bible/power-system/confirm").status_code == 200
    assert client.post(f"/api/projects/{project['project_id']}/bible/story-bible/confirm").status_code == 200
    return project



def test_generate_volume_chapter_scene_flow_and_confirm(client: TestClient, create_finalized_project) -> None:
    project = _prepare_ready_bible(client, create_finalized_project)

    volume_generate = client.post(f"/api/projects/{project['project_id']}/plans/volumes/generate")
    assert volume_generate.status_code == 201
    outline = volume_generate.json()
    assert outline["outline_status"] == "draft"
    first_volume_id = outline["volumes"][0]["volume_id"]

    outline_confirm = client.post(f"/api/projects/{project['project_id']}/plans/master-outline/confirm")
    assert outline_confirm.status_code == 200
    assert outline_confirm.json()["outline_status"] == "ready"

    volume_confirm = client.post(f"/api/projects/{project['project_id']}/plans/volumes/{first_volume_id}/confirm")
    assert volume_confirm.status_code == 200

    chapter_generate = client.post(
        f"/api/projects/{project['project_id']}/plans/volumes/{first_volume_id}/chapters/generate"
    )
    assert chapter_generate.status_code == 201
    first_chapter_id = chapter_generate.json()["items"][0]["chapter_id"]

    chapter_confirm = client.post(f"/api/projects/{project['project_id']}/plans/chapters/{first_chapter_id}/confirm")
    assert chapter_confirm.status_code == 200

    scene_generate = client.post(
        f"/api/projects/{project['project_id']}/plans/chapters/{first_chapter_id}/scenes/generate"
    )
    assert scene_generate.status_code == 201
    first_scene_id = scene_generate.json()["items"][0]["scene_id"]

    scene_confirm = client.post(f"/api/projects/{project['project_id']}/plans/scenes/{first_scene_id}/confirm")
    assert scene_confirm.status_code == 200



def test_generate_returns_409_when_target_exists_and_overwrite_false(client: TestClient, create_finalized_project) -> None:
    project = _prepare_ready_bible(client, create_finalized_project)

    first = client.post(f"/api/projects/{project['project_id']}/plans/volumes/generate")
    second = client.post(f"/api/projects/{project['project_id']}/plans/volumes/generate")

    assert first.status_code == 201
    assert second.status_code == 409

    volume_id = first.json()["volumes"][0]["volume_id"]
    client.post(f"/api/projects/{project['project_id']}/plans/master-outline/confirm")
    client.post(f"/api/projects/{project['project_id']}/plans/volumes/{volume_id}/confirm")

    third = client.post(f"/api/projects/{project['project_id']}/plans/volumes/{volume_id}/chapters/generate")
    fourth = client.post(f"/api/projects/{project['project_id']}/plans/volumes/{volume_id}/chapters/generate")
    assert third.status_code == 201
    assert fourth.status_code == 409

    chapter_id = third.json()["items"][0]["chapter_id"]
    client.post(f"/api/projects/{project['project_id']}/plans/chapters/{chapter_id}/confirm")
    fifth = client.post(f"/api/projects/{project['project_id']}/plans/chapters/{chapter_id}/scenes/generate")
    sixth = client.post(f"/api/projects/{project['project_id']}/plans/chapters/{chapter_id}/scenes/generate")
    assert fifth.status_code == 201
    assert sixth.status_code == 409



def test_confirm_stale_plan_returns_409(client: TestClient, create_finalized_project) -> None:
    project = _prepare_ready_bible(client, create_finalized_project)

    outline = client.post(f"/api/projects/{project['project_id']}/plans/volumes/generate").json()
    volume_id = outline["volumes"][0]["volume_id"]
    client.post(f"/api/projects/{project['project_id']}/plans/master-outline/confirm")
    client.post(f"/api/projects/{project['project_id']}/plans/volumes/{volume_id}/confirm")
    chapters = client.post(
        f"/api/projects/{project['project_id']}/plans/volumes/{volume_id}/chapters/generate"
    ).json()["items"]
    chapter_id = chapters[0]["chapter_id"]
    client.post(f"/api/projects/{project['project_id']}/plans/chapters/{chapter_id}/confirm")

    volume_patch = client.patch(
        f"/api/projects/{project['project_id']}/plans/volumes/{volume_id}",
        json={"summary": "卷摘要已更新"},
    )
    assert volume_patch.status_code == 200

    outline_response = client.get(f"/api/projects/{project['project_id']}/plans/master-outline")
    assert outline_response.status_code == 200
    assert outline_response.json()["outline_status"] == "stale"

    stale_confirm = client.post(f"/api/projects/{project['project_id']}/plans/chapters/{chapter_id}/confirm")
    assert stale_confirm.status_code == 409



def test_bible_update_stales_outline_volume_chapter_scene_chain(client: TestClient, create_finalized_project) -> None:
    project = _prepare_ready_bible(client, create_finalized_project)
    outline = client.post(f"/api/projects/{project['project_id']}/plans/volumes/generate").json()
    volume_id = outline["volumes"][0]["volume_id"]
    client.post(f"/api/projects/{project['project_id']}/plans/master-outline/confirm")
    client.post(f"/api/projects/{project['project_id']}/plans/volumes/{volume_id}/confirm")
    chapters = client.post(
        f"/api/projects/{project['project_id']}/plans/volumes/{volume_id}/chapters/generate"
    ).json()["items"]
    chapter_id = chapters[0]["chapter_id"]
    protagonist_id = client.get(f"/api/projects/{project['project_id']}/characters").json()["items"][0]["character_id"]
    chapter_patch = client.patch(
        f"/api/projects/{project['project_id']}/plans/chapters/{chapter_id}",
        json={"character_ids": [protagonist_id]},
    )
    assert chapter_patch.status_code == 200
    client.post(f"/api/projects/{project['project_id']}/plans/chapters/{chapter_id}/confirm")
    scenes = client.post(
        f"/api/projects/{project['project_id']}/plans/chapters/{chapter_id}/scenes/generate"
    ).json()["items"]
    scene_id = scenes[0]["scene_id"]

    patch = client.patch(
        f"/api/projects/{project['project_id']}/bible/story-bible",
        json={"story_promise": "触发全链路 stale"},
    )
    assert patch.status_code == 200

    outline_after = client.get(f"/api/projects/{project['project_id']}/plans/master-outline").json()
    volume_after = client.get(f"/api/projects/{project['project_id']}/plans/volumes/{volume_id}").json()
    chapter_after = client.get(f"/api/projects/{project['project_id']}/plans/chapters/{chapter_id}").json()
    scene_after = client.get(f"/api/projects/{project['project_id']}/plans/scenes/{scene_id}").json()
    assert outline_after["outline_status"] == "stale"
    assert volume_after["status"] == "stale"
    assert chapter_after["status"] == "stale"
    assert scene_after["status"] == "stale"



def test_plans_endpoint_returns_404_for_missing_project(client: TestClient) -> None:
    response = client.get("/api/projects/proj_missing/plans/master-outline")
    assert response.status_code == 404
