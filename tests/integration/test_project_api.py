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
