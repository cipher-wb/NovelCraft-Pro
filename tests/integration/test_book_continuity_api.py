from __future__ import annotations

import json
import os
from pathlib import Path

from fastapi.testclient import TestClient


def _project_root(slug: str) -> Path:
    return Path(os.environ["PROJECTS_ROOT"]) / slug


def _create_project_with_two_volumes(client: TestClient) -> dict[str, object]:
    project_response = client.post(
        "/api/projects",
        json={
            "title": "Book Continuity API测试书",
            "genre": "都市异能",
            "target_chapters": 4,
            "target_words": 400_000,
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
        json={"volume_count_hint": 2, "chapters_per_volume_hint": 1},
    )
    assert outline.status_code == 201
    assert client.post(f"/api/projects/{project_id}/plans/master-outline/confirm").status_code == 200
    volume_ids = []
    chapter_ids_by_volume: dict[str, list[str]] = {}
    for item in outline.json()["volumes"]:
        volume_id = item["volume_id"]
        volume_ids.append(volume_id)
        assert client.post(f"/api/projects/{project_id}/plans/volumes/{volume_id}/confirm").status_code == 200
        chapters = client.post(f"/api/projects/{project_id}/plans/volumes/{volume_id}/chapters/generate")
        assert chapters.status_code == 201
        chapter_ids_by_volume[volume_id] = [entry["chapter_id"] for entry in chapters.json()["items"]]
        for chapter_id in chapter_ids_by_volume[volume_id]:
            assert client.post(f"/api/projects/{project_id}/plans/chapters/{chapter_id}/confirm").status_code == 200
    return {
        "project_id": project_id,
        "slug": project["slug"],
        "volume_ids": volume_ids,
        "chapter_ids_by_volume": chapter_ids_by_volume,
    }


def _generate_and_accept(client: TestClient, project_id: str, scene_id: str) -> dict:
    generated = client.post(
        f"/api/projects/{project_id}/drafts/scenes/{scene_id}/generate",
        json={"mode": "outline_strict"},
    )
    assert generated.status_code == 201
    draft = generated.json()["draft"]
    accepted = client.post(f"/api/projects/{project_id}/drafts/{draft['draft_id']}/accept")
    assert accepted.status_code == 200
    return accepted.json()["draft"]


def _finalize_chapter(client: TestClient, project_id: str, chapter_id: str) -> None:
    scenes = client.post(
        f"/api/projects/{project_id}/plans/chapters/{chapter_id}/scenes/generate",
        json={"scene_count_hint": 1},
    )
    assert scenes.status_code == 201
    scene = scenes.json()["items"][0]
    assert client.post(f"/api/projects/{project_id}/plans/scenes/{scene['scene_id']}/confirm").status_code == 200
    _generate_and_accept(client, project_id, scene["scene_id"])
    assert client.post(f"/api/projects/{project_id}/chapters/{chapter_id}/assemble").status_code == 200
    assert client.post(f"/api/projects/{project_id}/chapters/{chapter_id}/finalize").status_code == 200


def _finalize_volume(client: TestClient, project_id: str, volume_id: str, chapter_ids: list[str]) -> None:
    for chapter_id in chapter_ids:
        _finalize_chapter(client, project_id, chapter_id)
    assert client.post(f"/api/projects/{project_id}/volumes/{volume_id}/assemble").status_code == 200
    assert client.post(f"/api/projects/{project_id}/volumes/{volume_id}/finalize").status_code == 200


def test_book_continuity_recheck_endpoint_overwrites_report_without_changing_status(client: TestClient) -> None:
    project = _create_project_with_two_volumes(client)
    for volume_id in project["volume_ids"]:
        _finalize_volume(client, project["project_id"], volume_id, project["chapter_ids_by_volume"][volume_id])

    assert client.post(f"/api/projects/{project['project_id']}/book/assemble").status_code == 200
    latest = client.get(f"/api/projects/{project['project_id']}/book/continuity-checks/latest")
    assert latest.status_code == 200
    initial_report_id = latest.json()["report"]["report_id"]

    rechecked = client.post(f"/api/projects/{project['project_id']}/book/continuity-checks/recheck")
    assert rechecked.status_code == 200
    assert rechecked.json()["report"]["report_id"] != initial_report_id
    assert client.get(f"/api/projects/{project['project_id']}/book/assembled").json()["status"] == "assembled"


def test_book_finalize_is_blocked_by_continuity_api(client: TestClient) -> None:
    project = _create_project_with_two_volumes(client)
    for volume_id in project["volume_ids"]:
        _finalize_volume(client, project["project_id"], volume_id, project["chapter_ids_by_volume"][volume_id])

    project_root = _project_root(project["slug"])
    story_bible_path = project_root / "bible" / "story_bible.json"
    story_bible = json.loads(story_bible_path.read_text(encoding="utf-8"))
    story_bible["protagonist_ids"] = ["char_missing_mc"]
    story_bible_path.write_text(json.dumps(story_bible, ensure_ascii=False, indent=2), encoding="utf-8")

    assert client.post(f"/api/projects/{project['project_id']}/book/assemble").status_code == 200
    finalize = client.post(f"/api/projects/{project['project_id']}/book/finalize")
    assert finalize.status_code == 409


def test_book_finalize_succeeds_on_warning_only_continuity(client: TestClient) -> None:
    project = _create_project_with_two_volumes(client)
    for volume_id in project["volume_ids"]:
        _finalize_volume(client, project["project_id"], volume_id, project["chapter_ids_by_volume"][volume_id])

    project_root = _project_root(project["slug"])
    accepted_path = project_root / "memory" / "accepted_scenes.json"
    accepted = json.loads(accepted_path.read_text(encoding="utf-8"))
    accepted["items"] = [
        item for item in accepted["items"] if item["volume_id"] != project["volume_ids"][-1]
    ]
    accepted_path.write_text(json.dumps(accepted, ensure_ascii=False, indent=2), encoding="utf-8")

    assert client.post(f"/api/projects/{project['project_id']}/book/assemble").status_code == 200
    finalize = client.post(f"/api/projects/{project['project_id']}/book/finalize")
    assert finalize.status_code == 200
