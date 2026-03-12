from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient



def test_create_project_creates_manifest_and_directories(
    client: TestClient, temp_roots: dict[str, Path]
) -> None:
    response = client.post(
        "/api/projects",
        json={
            "title": "我的新书",
            "genre": "修仙爽文",
            "target_chapters": 300,
            "target_words": 2_000_000
        }
    )

    assert response.status_code == 201
    payload = response.json()
    slug = payload["slug"]

    project_root = temp_roots["projects_root"] / slug
    manifest_path = project_root / "project.json"

    assert project_root.exists()
    assert manifest_path.exists()
    assert payload["manifest"]["title"] == "我的新书"


def test_project_read_endpoints_return_created_project(
    client: TestClient, temp_roots: dict[str, Path]
) -> None:
    create_response = client.post(
        "/api/projects",
        json={
            "title": "长夜行",
            "genre": "都市异能",
            "target_chapters": 200,
            "target_words": 1_200_000,
        },
    )
    assert create_response.status_code == 201
    created = create_response.json()

    list_response = client.get("/api/projects")
    assert list_response.status_code == 200
    list_payload = list_response.json()
    assert len(list_payload["items"]) == 1
    assert list_payload["items"][0]["project_id"] == created["project_id"]

    detail_response = client.get(f"/api/projects/{created['project_id']}")
    assert detail_response.status_code == 200
    detail_payload = detail_response.json()
    assert detail_payload["manifest"]["project_id"] == created["project_id"]
    assert detail_payload["paths"]["root"].endswith(created["slug"])
