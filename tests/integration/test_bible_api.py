from __future__ import annotations

from fastapi.testclient import TestClient



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
