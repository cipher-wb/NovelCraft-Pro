from __future__ import annotations

import json
import os
from pathlib import Path

from fastapi.testclient import TestClient


def _project_root(slug: str) -> Path:
    return Path(os.environ["PROJECTS_ROOT"]) / slug


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _create_ready_project(client: TestClient) -> dict[str, object]:
    project_response = client.post(
        "/api/projects",
        json={
            "title": "Productization API测试书",
            "genre": "都市异能",
            "target_chapters": 4,
            "target_words": 300_000,
        },
    )
    project = project_response.json()
    start = client.post(
        f"/api/projects/{project['project_id']}/consultant/sessions",
        json={
            "brief": "都市修真长线升级",
            "preferred_subgenres": ["都市异能", "升级流"],
            "constraints": ["作者主导", "长线连载"],
        },
    )
    session_id = start.json()["session_id"]
    answers = {
        "market_hook": "社畜重生后靠系统逆袭修仙",
        "target_audience": "男频爽文读者",
        "protagonist_design": "隐忍后爆发的主角",
        "golden_finger_design": "功德兑换系统",
        "core_conflict_engine": "隐世势力与现代秩序冲突",
        "early_30_chapter_pacing": "前10章觉醒，中10章立威，后10章破局",
    }
    question = start.json()["current_question"]
    while question is not None:
        state = client.post(
            f"/api/consultant/sessions/{session_id}/answer",
            json={"question_id": question["question_id"], "answer": answers[question["question_id"]]},
        )
        question = state.json()["current_question"]
    assert client.post(f"/api/consultant/sessions/{session_id}/finalize").status_code == 200

    project_id = project["project_id"]
    assert client.post(f"/api/projects/{project_id}/bible/from-consultant").status_code == 201
    assert client.post(f"/api/projects/{project_id}/characters/confirm").status_code == 200
    assert client.post(f"/api/projects/{project_id}/bible/world/confirm").status_code == 200
    assert client.post(f"/api/projects/{project_id}/bible/power-system/confirm").status_code == 200
    assert client.post(f"/api/projects/{project_id}/bible/story-bible/confirm").status_code == 200

    outline = client.post(
        f"/api/projects/{project_id}/plans/volumes/generate",
        json={"volume_count_hint": 1, "chapters_per_volume_hint": 2},
    )
    assert outline.status_code == 201
    volume_id = outline.json()["volumes"][0]["volume_id"]
    assert client.post(f"/api/projects/{project_id}/plans/master-outline/confirm").status_code == 200
    assert client.post(f"/api/projects/{project_id}/plans/volumes/{volume_id}/confirm").status_code == 200
    chapters = client.post(f"/api/projects/{project_id}/plans/volumes/{volume_id}/chapters/generate")
    assert chapters.status_code == 201
    chapter_ids = [item["chapter_id"] for item in chapters.json()["items"]]
    scene_ids_by_chapter: dict[str, list[str]] = {}
    for chapter_id in chapter_ids:
        assert client.post(f"/api/projects/{project_id}/plans/chapters/{chapter_id}/confirm").status_code == 200
        scenes = client.post(
            f"/api/projects/{project_id}/plans/chapters/{chapter_id}/scenes/generate",
            json={"scene_count_hint": 2},
        )
        assert scenes.status_code == 201
        scene_ids = [item["scene_id"] for item in scenes.json()["items"]]
        scene_ids_by_chapter[chapter_id] = scene_ids
        for scene_id in scene_ids:
            assert client.post(f"/api/projects/{project_id}/plans/scenes/{scene_id}/confirm").status_code == 200
            draft = client.post(
                f"/api/projects/{project_id}/drafts/scenes/{scene_id}/generate",
                json={"mode": "outline_strict"},
            )
            assert draft.status_code == 201
            draft_id = draft.json()["draft"]["draft_id"]
            assert client.post(f"/api/projects/{project_id}/drafts/{draft_id}/accept").status_code == 200

    for chapter_id in chapter_ids:
        assert client.post(f"/api/projects/{project_id}/chapters/{chapter_id}/assemble").status_code == 200
        assert client.post(f"/api/projects/{project_id}/chapters/{chapter_id}/finalize").status_code == 200
    assert client.post(f"/api/projects/{project_id}/volumes/{volume_id}/assemble").status_code == 200
    assert client.post(f"/api/projects/{project_id}/volumes/{volume_id}/finalize").status_code == 200
    assert client.post(f"/api/projects/{project_id}/book/assemble").status_code == 200
    assert client.post(f"/api/projects/{project_id}/book/finalize").status_code == 200

    return {
        "project_id": project_id,
        "slug": project["slug"],
        "volume_id": volume_id,
        "chapter_id": chapter_ids[0],
        "scene_id": scene_ids_by_chapter[chapter_ids[0]][0],
    }


def test_export_api_supports_scene_chapter_volume_and_book_packages(client: TestClient) -> None:
    project = _create_ready_project(client)

    for scope, target_id in [
        ("scene", project["scene_id"]),
        ("chapter", project["chapter_id"]),
        ("volume", project["volume_id"]),
        ("book", "book"),
    ]:
        response = client.post(
            f"/api/projects/{project['project_id']}/export",
            json={"scope": scope, "target_id": target_id, "format": "markdown_package"},
        )
        assert response.status_code == 200
        payload = response.json()
        assert payload["scope"] == scope
        manifest = json.loads((_project_root(project["slug"]) / payload["relative_dir"] / "manifest.json").read_text(encoding="utf-8"))
        assert manifest["scope"] == scope
        assert "included_files" in manifest


def test_project_package_export_and_import_api_are_available(client: TestClient) -> None:
    project = _create_ready_project(client)

    export_response = client.post(
        f"/api/projects/{project['project_id']}/export",
        json={"scope": "project", "format": "json_package"},
    )
    assert export_response.status_code == 200
    export_payload = export_response.json()
    package_root = _project_root(project["slug"]) / export_payload["relative_dir"]
    manifest = json.loads((package_root / "manifest.json").read_text(encoding="utf-8"))
    inventory = json.loads((package_root / "inventory.json").read_text(encoding="utf-8"))
    assert manifest["scope"] == "project"
    assert manifest["package_version"] == "project_package_v1"
    assert inventory["package_version"] == "project_package_v1"

    imported = client.post(
        "/api/projects/import-package",
        json={
            "package_path": str(package_root),
            "new_project_slug": f"{project['slug']}-imported",
            "mode": "create_new",
        },
    )
    assert imported.status_code == 200
    imported_payload = imported.json()
    assert imported_payload["mode"] == "create_new"
    assert imported_payload["post_import_health"]["project_id"] == imported_payload["project_id"]


def test_rebuild_and_health_api_are_available_and_dashboard_links_exist(client: TestClient) -> None:
    project = _create_ready_project(client)
    root = _project_root(project["slug"])
    (root / "memory" / "book_summary.json").unlink()

    health = client.get(f"/api/projects/{project['project_id']}/diagnostics/health")
    assert health.status_code == 200
    health_payload = health.json()
    assert "actionable_items" in health_payload
    assert "overall_status" in health_payload

    rebuild = client.post(f"/api/projects/{project['project_id']}/rebuild", json={})
    assert rebuild.status_code == 200
    assert rebuild.json()["targets"] == ["memory", "chapters", "volumes", "book", "checks"]
    assert (root / "memory" / "book_summary.json").exists()

    dashboard = client.get("/studio")
    assert dashboard.status_code == 200
    assert "Rebuild All" in dashboard.text
    assert "Project Health" in dashboard.text

    scene_page = client.get("/studio/scene.html")
    chapter_page = client.get("/studio/chapter.html")
    volume_page = client.get("/studio/volume.html")
    book_page = client.get("/studio/book.html")
    assert "Export Scene" in scene_page.text
    assert "Export Chapter" in chapter_page.text
    assert "Export Volume" in volume_page.text
    assert "Export Book" in book_page.text


def test_archive_backup_and_snapshots_api_are_available(client: TestClient) -> None:
    project = _create_ready_project(client)

    archive = client.post(
        f"/api/projects/{project['project_id']}/archive-snapshot",
        json={"label": "release-candidate"},
    )
    assert archive.status_code == 200
    archive_payload = archive.json()
    assert archive_payload["snapshot_type"] == "archive"
    assert archive_payload["label"] == "release-candidate"

    backup = client.post(f"/api/projects/{project['project_id']}/backup", json={})
    assert backup.status_code == 200
    backup_payload = backup.json()
    assert backup_payload["snapshot_type"] == "backup"

    snapshots = client.get(f"/api/projects/{project['project_id']}/snapshots")
    assert snapshots.status_code == 200
    items = snapshots.json()["items"]
    assert items
    assert {item["snapshot_type"] for item in items}.issuperset({"archive", "backup"})

    dashboard = client.get("/studio")
    assert dashboard.status_code == 200
    assert "Import Package" in dashboard.text
    assert "Create Archive Snapshot" in dashboard.text
    assert "Create Backup" in dashboard.text


def test_productization_endpoints_return_machine_friendly_error_codes(client: TestClient) -> None:
    export = client.post(
        "/api/projects/proj_missing/export",
        json={"scope": "unsupported_scope", "target_id": "anything", "format": "json_package"},
    )
    assert export.status_code == 400
    assert export.json()["detail"]["code"] == "unsupported_export_scope"

    health = client.get("/api/projects/proj_missing/diagnostics/health")
    assert health.status_code == 404
    assert health.json()["detail"]["code"] == "resource_not_found"

    imported = client.post(
        "/api/projects/import-package",
        json={"package_path": "examples/sample-project-package", "mode": "overwrite_existing"},
    )
    assert imported.status_code == 400
    assert imported.json()["detail"]["code"] == "unsupported_import_mode"


def test_import_conflict_returns_stable_target_slug_code(client: TestClient) -> None:
    project = _create_ready_project(client)

    exported = client.post(
        f"/api/projects/{project['project_id']}/export",
        json={"scope": "project", "format": "json_package"},
    )
    assert exported.status_code == 200
    package_root = _project_root(project["slug"]) / exported.json()["relative_dir"]

    first = client.post(
        "/api/projects/import-package",
        json={
            "package_path": str(package_root),
            "new_project_slug": f"{project['slug']}-phase11-import",
            "mode": "create_new",
        },
    )
    assert first.status_code == 200

    second = client.post(
        "/api/projects/import-package",
        json={
            "package_path": str(package_root),
            "new_project_slug": f"{project['slug']}-phase11-import",
            "mode": "create_new",
        },
    )
    assert second.status_code == 409
    assert second.json()["detail"]["code"] == "target_slug_exists"


def test_committed_sample_project_package_is_importable_and_health_is_clean(client: TestClient) -> None:
    sample_package = _repo_root() / "examples" / "sample-project-package"
    imported = client.post(
        "/api/projects/import-package",
        json={
            "package_path": str(sample_package),
            "new_project_id": "proj_phase11_sample_api",
            "new_project_slug": "phase11-sample-api",
            "mode": "create_new",
        },
    )
    assert imported.status_code == 200
    payload = imported.json()
    assert payload["package_version"] == "project_package_v1"
    assert payload["project_id"] == "proj_phase11_sample_api"
    assert payload["project_slug"] == "phase11-sample-api"
    assert payload["post_import_health"]["overall_status"] == "clean"

    health = client.get("/api/projects/proj_phase11_sample_api/diagnostics/health")
    assert health.status_code == 200
    assert health.json()["overall_status"] == "clean"
