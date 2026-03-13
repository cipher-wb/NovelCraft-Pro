from __future__ import annotations

import json
import os
from pathlib import Path

from fastapi.testclient import TestClient


def _project_root(slug: str) -> Path:
    return Path(os.environ["PROJECTS_ROOT"]) / slug


def _create_small_project(client: TestClient) -> dict[str, str]:
    project_response = client.post(
        "/api/projects",
        json={
            "title": "Volume API测试书",
            "genre": "都市异能",
            "target_chapters": 2,
            "target_words": 200_000,
        },
    )
    project = project_response.json()
    start = client.post(
        f"/api/projects/{project['project_id']}/consultant/sessions",
        json={
            "brief": "都市修仙打脸升级流",
            "preferred_subgenres": ["都市异能", "升级流"],
            "constraints": ["作者主导", "长线连载"],
        },
    )
    session_id = start.json()["session_id"]
    answers = {
        "market_hook": "社畜重生后靠功德系统在都市修仙打脸",
        "target_audience": "男频爽文读者",
        "protagonist_design": "隐忍型主角，前期受辱后快速崛起",
        "golden_finger_design": "功德兑换系统",
        "core_conflict_engine": "凡俗社会秩序与修真隐世势力冲突",
        "early_30_chapter_pacing": "前10章受辱觉醒，中10章立威，中后10章破局",
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
    return {
        "project_id": project_id,
        "slug": project["slug"],
        "volume_id": volume_id,
        "chapter_ids": [item["chapter_id"] for item in chapters.json()["items"][:2]],
    }


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


def _finalize_chapter(client: TestClient, project_id: str, chapter_id: str) -> dict:
    assert client.post(f"/api/projects/{project_id}/plans/chapters/{chapter_id}/confirm").status_code == 200
    scenes = client.post(
        f"/api/projects/{project_id}/plans/chapters/{chapter_id}/scenes/generate",
        json={"scene_count_hint": 2},
    )
    assert scenes.status_code == 201
    for index, scene in enumerate(scenes.json()["items"]):
        assert client.post(f"/api/projects/{project_id}/plans/scenes/{scene['scene_id']}/confirm").status_code == 200
        _generate_and_accept(client, project_id, scene["scene_id"], mode="momentum" if index % 2 else "outline_strict")
    assembled = client.post(f"/api/projects/{project_id}/chapters/{chapter_id}/assemble")
    assert assembled.status_code == 200
    finalized = client.post(f"/api/projects/{project_id}/chapters/{chapter_id}/finalize")
    assert finalized.status_code == 200
    return finalized.json()["assembled"]


def test_volume_api_assemble_recheck_finalize_and_memory_flow(client: TestClient) -> None:
    project = _create_small_project(client)
    finalized_one = _finalize_chapter(client, project["project_id"], project["chapter_ids"][0])
    finalized_two = _finalize_chapter(client, project["project_id"], project["chapter_ids"][1])

    assembled = client.post(f"/api/projects/{project['project_id']}/volumes/{project['volume_id']}/assemble")
    assert assembled.status_code == 200
    payload = assembled.json()
    assert payload["assembled"]["status"] == "assembled"
    assert payload["check_report"]["overall_status"] == "clean"
    assert payload["assembled"]["chapter_order"][0]["assembled_version"] == finalized_one["version"]
    assert payload["assembled"]["chapter_order"][1]["assembled_version"] == finalized_two["version"]

    fetched = client.get(f"/api/projects/{project['project_id']}/volumes/{project['volume_id']}/assembled")
    assert fetched.status_code == 200
    assert fetched.json()["status"] == "assembled"

    rechecked = client.post(f"/api/projects/{project['project_id']}/volumes/{project['volume_id']}/checks/recheck")
    assert rechecked.status_code == 200
    assert rechecked.json()["report"]["overall_status"] == "clean"

    finalized = client.post(f"/api/projects/{project['project_id']}/volumes/{project['volume_id']}/finalize")
    assert finalized.status_code == 200
    assert finalized.json()["assembled"]["status"] == "finalized"

    memory_path = _project_root(project["slug"]) / "memory" / "volume_summaries.json"
    memory_payload = json.loads(memory_path.read_text(encoding="utf-8"))
    item = next(entry for entry in memory_payload["items"] if entry["volume_id"] == project["volume_id"])
    assert item["summary"] == finalized.json()["assembled"]["summary"]


def test_volume_api_partial_assemble_blocks_finalize_and_stale_flow(client: TestClient) -> None:
    project = _create_small_project(client)
    _finalize_chapter(client, project["project_id"], project["chapter_ids"][0])

    assembled = client.post(f"/api/projects/{project['project_id']}/volumes/{project['volume_id']}/assemble")
    assert assembled.status_code == 200
    assert assembled.json()["check_report"]["overall_status"] == "blocked"

    finalize = client.post(f"/api/projects/{project['project_id']}/volumes/{project['volume_id']}/finalize")
    assert finalize.status_code == 409

    _finalize_chapter(client, project["project_id"], project["chapter_ids"][1])
    reassembled = client.post(f"/api/projects/{project['project_id']}/volumes/{project['volume_id']}/assemble")
    assert reassembled.status_code == 200
    assert reassembled.json()["check_report"]["overall_status"] == "clean"

    finalized = client.post(f"/api/projects/{project['project_id']}/volumes/{project['volume_id']}/finalize")
    assert finalized.status_code == 200

    replacement = client.post(
        f"/api/projects/{project['project_id']}/drafts/scenes/scene_0001_001/generate",
        json={"mode": "momentum"},
    )
    assert replacement.status_code == 201
    replacement_id = replacement.json()["draft"]["draft_id"]
    assert client.post(f"/api/projects/{project['project_id']}/drafts/{replacement_id}/accept").status_code == 200
    assert client.get(f"/api/projects/{project['project_id']}/chapters/{project['chapter_ids'][0]}/assembled").json()["status"] == "stale"

    stale = client.get(f"/api/projects/{project['project_id']}/volumes/{project['volume_id']}/assembled")
    assert stale.status_code == 200
    assert stale.json()["status"] == "stale"

    recheck = client.post(f"/api/projects/{project['project_id']}/volumes/{project['volume_id']}/checks/recheck")
    assert recheck.status_code == 200
    assert client.get(f"/api/projects/{project['project_id']}/volumes/{project['volume_id']}/assembled").json()["status"] == "stale"

    assert client.post(f"/api/projects/{project['project_id']}/volumes/{project['volume_id']}/finalize").status_code == 409


def test_volume_studio_page_is_available(client: TestClient) -> None:
    response = client.get("/studio/volume.html")
    assert response.status_code == 200
    assert "Assemble Volume" in response.text
