from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient



def test_consultant_flow_runs_start_answer_finalize(
    client: TestClient, temp_roots: dict[str, Path]
) -> None:
    project_response = client.post(
        "/api/projects",
        json={
            "title": "都市修仙录",
            "genre": "都市异能",
            "target_chapters": 180,
            "target_words": 1_500_000
        }
    )
    project_id = project_response.json()["project_id"]
    slug = project_response.json()["slug"]

    start_response = client.post(
        f"/api/projects/{project_id}/consultant/sessions",
        json={
            "brief": "想写一本都市修仙打脸升级流",
            "preferred_subgenres": ["都市异能", "升级流"],
            "constraints": ["作者主导", "长线连载"]
        }
    )
    assert start_response.status_code == 201

    session_id = start_response.json()["session_id"]
    question = start_response.json()["current_question"]

    answers = {
        "market_hook": "社畜重生后靠功德系统在都市修仙打脸",
        "target_audience": "男频爽文读者",
        "protagonist_design": "隐忍型主角，前期受辱后快速崛起",
        "golden_finger_design": "功德兑换系统",
        "core_conflict_engine": "凡俗社会秩序与修真隐世势力冲突",
        "early_30_chapter_pacing": "前10章受辱觉醒，中10章立威，中后10章破局"
    }

    while question is not None:
        answer_response = client.post(
            f"/api/consultant/sessions/{session_id}/answer",
            json={
                "question_id": question["question_id"],
                "answer": answers[question["question_id"]]
            }
        )
        assert answer_response.status_code == 200
        question = answer_response.json()["current_question"]

    finalize_response = client.post(f"/api/consultant/sessions/{session_id}/finalize")
    assert finalize_response.status_code == 200

    dossier_path = temp_roots["projects_root"] / slug / "consultant" / "dossier.json"
    assert dossier_path.exists()
    assert finalize_response.json()["dossier"]["project_id"] == project_id
