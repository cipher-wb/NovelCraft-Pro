from __future__ import annotations

from fastapi.testclient import TestClient



def _create_finalized_project(client: TestClient) -> dict[str, str]:
    project_response = client.post(
        "/api/projects",
        json={
            "title": "Bible API测试书",
            "genre": "都市异能",
            "target_chapters": 120,
            "target_words": 1_000_000,
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
    finalize = client.post(f"/api/consultant/sessions/{session_id}/finalize")
    assert finalize.status_code == 200
    return {"project_id": project["project_id"], "slug": project["slug"]}



def test_bible_from_consultant_and_aggregate_read(client: TestClient) -> None:
    project = _create_finalized_project(client)

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



def test_story_bible_confirm_requires_featured_references_resolvable(client: TestClient) -> None:
    project = _create_finalized_project(client)
    client.post(f"/api/projects/{project['project_id']}/bible/from-consultant")

    patch = client.patch(
        f"/api/projects/{project['project_id']}/bible/story-bible",
        json={"featured_faction_ids": ["missing_faction"]},
    )
    assert patch.status_code == 200

    confirm = client.post(f"/api/projects/{project['project_id']}/bible/story-bible/confirm")
    assert confirm.status_code == 400



def test_character_crud_requires_reconfirm(client: TestClient) -> None:
    project = _create_finalized_project(client)
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
