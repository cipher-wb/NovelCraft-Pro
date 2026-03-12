from __future__ import annotations

from pathlib import Path

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



def test_bible_from_consultant_and_aggregate_read(client: TestClient, create_finalized_project) -> None:
    project = create_finalized_project()

    create = client.post(f"/api/projects/{project['project_id']}/bible/from-consultant")
    assert create.status_code == 201

    aggregate = client.get(f"/api/projects/{project['project_id']}/bible")
    assert aggregate.status_code == 200
    payload = aggregate.json()
    assert payload["story_bible"]["project_id"] == project["project_id"]
    assert payload["characters"]["items"]



def test_bible_from_consultant_returns_400_when_dossier_missing(client: TestClient) -> None:
    project_response = client.post(
        "/api/projects",
        json={
            "title": "无档案项目",
            "genre": "都市异能",
            "target_chapters": 120,
            "target_words": 1_000_000,
        },
    )
    project_id = project_response.json()["project_id"]

    response = client.post(f"/api/projects/{project_id}/bible/from-consultant")
    assert response.status_code == 400



def test_story_bible_confirm_requires_featured_references_resolvable(client: TestClient, create_finalized_project) -> None:
    project = create_finalized_project()
    client.post(f"/api/projects/{project['project_id']}/bible/from-consultant")

    patch = client.patch(
        f"/api/projects/{project['project_id']}/bible/story-bible",
        json={"featured_faction_ids": ["missing_faction"]},
    )
    assert patch.status_code == 200

    confirm = client.post(f"/api/projects/{project['project_id']}/bible/story-bible/confirm")
    assert confirm.status_code == 400



def test_character_crud_requires_reconfirm(client: TestClient, create_finalized_project) -> None:
    project = create_finalized_project()
    client.post(f"/api/projects/{project['project_id']}/bible/from-consultant")

    confirm = client.post(f"/api/projects/{project['project_id']}/characters/confirm")
    assert confirm.status_code == 200

    create_character = client.post(
        f"/api/projects/{project['project_id']}/characters",
        json={"name": "新角色", "role": "support", "is_protagonist": False, "traits": ["冷静"]},
    )
    assert create_character.status_code == 201

    characters = client.get(f"/api/projects/{project['project_id']}/characters")
    assert characters.status_code == 200
    assert characters.json()["status"] == "draft"



def test_stale_story_bible_confirm_returns_409(
    client: TestClient, create_finalized_project, temp_roots: dict[str, Path]
) -> None:
    project = create_finalized_project()
    client.post(f"/api/projects/{project['project_id']}/bible/from-consultant")

    story_bible_path = temp_roots["projects_root"] / project["slug"] / "bible" / "story_bible.json"
    import json

    payload = json.loads(story_bible_path.read_text(encoding="utf-8"))
    payload["status"] = "stale"
    story_bible_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    response = client.post(f"/api/projects/{project['project_id']}/bible/story-bible/confirm")
    assert response.status_code == 409



def test_delete_referenced_character_returns_409(client: TestClient, create_finalized_project) -> None:
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
    patch = client.patch(
        f"/api/projects/{project['project_id']}/plans/chapters/{chapter_id}",
        json={"character_ids": [protagonist_id]},
    )
    assert patch.status_code == 200

    response = client.delete(f"/api/projects/{project['project_id']}/characters/{protagonist_id}")
    assert response.status_code == 409
