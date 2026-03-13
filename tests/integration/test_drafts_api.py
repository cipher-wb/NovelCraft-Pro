from __future__ import annotations

import os
from pathlib import Path

import pytest

from fastapi.testclient import TestClient



def _project_root(slug: str) -> Path:
    return Path(os.environ["PROJECTS_ROOT"]) / slug


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


def _create_two_volume_project(client: TestClient, create_finalized_project) -> dict[str, object]:
    project = create_finalized_project()
    project_id = project["project_id"]

    assert client.post(f"/api/projects/{project_id}/bible/from-consultant").status_code == 201
    assert client.post(f"/api/projects/{project_id}/characters/confirm").status_code == 200
    assert client.post(f"/api/projects/{project_id}/bible/world/confirm").status_code == 200
    assert client.post(f"/api/projects/{project_id}/bible/power-system/confirm").status_code == 200
    assert client.post(f"/api/projects/{project_id}/bible/story-bible/confirm").status_code == 200

    outline = client.post(
        f"/api/projects/{project_id}/plans/volumes/generate",
        json={"volume_count_hint": 2, "chapters_per_volume_hint": 3},
    )
    assert outline.status_code == 201
    volumes = outline.json()["volumes"]
    volume_one_id = volumes[0]["volume_id"]
    volume_two_id = volumes[1]["volume_id"]
    assert client.post(f"/api/projects/{project_id}/plans/master-outline/confirm").status_code == 200
    assert client.post(f"/api/projects/{project_id}/plans/volumes/{volume_one_id}/confirm").status_code == 200
    assert client.post(f"/api/projects/{project_id}/plans/volumes/{volume_two_id}/confirm").status_code == 200

    chapters_one = client.post(f"/api/projects/{project_id}/plans/volumes/{volume_one_id}/chapters/generate")
    chapters_two = client.post(f"/api/projects/{project_id}/plans/volumes/{volume_two_id}/chapters/generate")
    assert chapters_one.status_code == 201
    assert chapters_two.status_code == 201
    chapter_ids_one = [item["chapter_id"] for item in chapters_one.json()["items"]]
    chapter_ids_two = [item["chapter_id"] for item in chapters_two.json()["items"]]

    def _finalize_chapter(chapter_id: str) -> None:
        assert client.post(f"/api/projects/{project_id}/plans/chapters/{chapter_id}/confirm").status_code == 200
        scenes = client.post(
            f"/api/projects/{project_id}/plans/chapters/{chapter_id}/scenes/generate",
            json={"scene_count_hint": 1},
        )
        assert scenes.status_code == 201
        scene_id = scenes.json()["items"][0]["scene_id"]
        assert client.post(f"/api/projects/{project_id}/plans/scenes/{scene_id}/confirm").status_code == 200
        _generate_and_accept(client, project_id, scene_id)
        assert client.post(f"/api/projects/{project_id}/chapters/{chapter_id}/assemble").status_code == 200
        assert client.post(f"/api/projects/{project_id}/chapters/{chapter_id}/finalize").status_code == 200

    for chapter_id in chapter_ids_one:
        _finalize_chapter(chapter_id)
    assert client.post(f"/api/projects/{project_id}/volumes/{volume_one_id}/assemble").status_code == 200
    assert client.post(f"/api/projects/{project_id}/volumes/{volume_one_id}/finalize").status_code == 200

    scene_ids_two: list[str] = []
    for chapter_id in chapter_ids_two:
        assert client.post(f"/api/projects/{project_id}/plans/chapters/{chapter_id}/confirm").status_code == 200
        scenes = client.post(
            f"/api/projects/{project_id}/plans/chapters/{chapter_id}/scenes/generate",
            json={"scene_count_hint": 1},
        )
        assert scenes.status_code == 201
        scene_id = scenes.json()["items"][0]["scene_id"]
        scene_ids_two.append(scene_id)
        assert client.post(f"/api/projects/{project_id}/plans/scenes/{scene_id}/confirm").status_code == 200

    return {
        "project_id": project_id,
        "slug": project["slug"],
        "volume_one_id": volume_one_id,
        "volume_two_id": volume_two_id,
        "chapter_ids_two": chapter_ids_two,
        "scene_ids_two": scene_ids_two,
    }



def test_scene_draft_generate_accept_reject_flow(client: TestClient, build_ready_scene_project) -> None:
    project = build_ready_scene_project(confirm_scene=True)

    generated = client.post(
        f"/api/projects/{project['project_id']}/drafts/scenes/{project['scene_id']}/generate",
        json={"mode": "outline_strict"},
    )
    assert generated.status_code == 201
    payload = generated.json()
    draft_id = payload["draft"]["draft_id"]
    assert payload["check_report"]["overall_status"] == "clean"

    latest_report = client.get(f"/api/projects/{project['project_id']}/drafts/{draft_id}/checks/latest")
    assert latest_report.status_code == 200
    assert latest_report.json()["report"]["draft_id"] == draft_id

    manifest = client.get(f"/api/projects/{project['project_id']}/drafts/scenes/{project['scene_id']}")
    assert manifest.status_code == 200
    assert manifest.json()["latest_draft_id"] == draft_id
    assert manifest.json()["accepted_draft_id"] is None

    rejected = client.post(f"/api/projects/{project['project_id']}/drafts/{draft_id}/reject")
    assert rejected.status_code == 200
    assert rejected.json()["draft"]["status"] == "rejected"

    generated_two = client.post(
        f"/api/projects/{project['project_id']}/drafts/scenes/{project['scene_id']}/generate",
        json={"mode": "momentum"},
    )
    assert generated_two.status_code == 201
    draft_two_id = generated_two.json()["draft"]["draft_id"]

    accepted = client.post(f"/api/projects/{project['project_id']}/drafts/{draft_two_id}/accept")
    assert accepted.status_code == 200
    assert accepted.json()["draft"]["status"] == "accepted"

    manifest_after = client.get(f"/api/projects/{project['project_id']}/drafts/scenes/{project['scene_id']}")
    assert manifest_after.status_code == 200
    assert manifest_after.json()["latest_draft_id"] == draft_two_id
    assert manifest_after.json()["accepted_draft_id"] == draft_two_id



def test_scene_draft_generate_returns_409_when_scene_not_ready(client: TestClient, build_ready_scene_project) -> None:
    project = build_ready_scene_project(confirm_scene=False)

    response = client.post(
        f"/api/projects/{project['project_id']}/drafts/scenes/{project['scene_id']}/generate",
        json={"mode": "outline_strict"},
    )
    assert response.status_code == 409



def test_accept_reject_on_non_draft_returns_409(client: TestClient, build_ready_scene_project) -> None:
    project = build_ready_scene_project(confirm_scene=True)

    generated = client.post(
        f"/api/projects/{project['project_id']}/drafts/scenes/{project['scene_id']}/generate",
        json={"mode": "outline_strict"},
    )
    draft_id = generated.json()["draft"]["draft_id"]

    accepted = client.post(f"/api/projects/{project['project_id']}/drafts/{draft_id}/accept")
    assert accepted.status_code == 200

    accept_again = client.post(f"/api/projects/{project['project_id']}/drafts/{draft_id}/accept")
    reject_after_accept = client.post(f"/api/projects/{project['project_id']}/drafts/{draft_id}/reject")
    assert accept_again.status_code == 409
    assert reject_after_accept.status_code == 409



def test_generate_uses_retrieved_memory_from_previous_accepted_scene(client: TestClient, build_ready_scene_project) -> None:
    project = build_ready_scene_project(confirm_scene=True)
    second_scene_id = project["scene_ids"][1]
    assert client.post(f"/api/projects/{project['project_id']}/plans/scenes/{second_scene_id}/confirm").status_code == 200

    first_generated = client.post(
        f"/api/projects/{project['project_id']}/drafts/scenes/{project['scene_id']}/generate",
        json={"mode": "outline_strict"},
    )
    assert first_generated.status_code == 201
    first_draft_id = first_generated.json()["draft"]["draft_id"]
    assert client.post(f"/api/projects/{project['project_id']}/drafts/{first_draft_id}/accept").status_code == 200

    second_generated = client.post(
        f"/api/projects/{project['project_id']}/drafts/scenes/{second_scene_id}/generate",
        json={"mode": "outline_strict"},
    )
    assert second_generated.status_code == 201
    retrieved = second_generated.json()["context_bundle"]["retrieved_memory"]
    assert retrieved["recent_scene_summaries"][0]["scene_id"] == project["scene_id"]



def test_recheck_endpoint_refreshes_draft_summary_fields(client: TestClient, build_ready_scene_project) -> None:
    project = build_ready_scene_project(confirm_scene=True)
    generated = client.post(
        f"/api/projects/{project['project_id']}/drafts/scenes/{project['scene_id']}/generate",
        json={"mode": "outline_strict"},
    )
    assert generated.status_code == 201
    draft = generated.json()["draft"]
    old_run_id = draft["latest_check_run_id"]

    draft_path = _project_root(project["slug"]) / draft["draft_path"]
    payload = __import__("json").loads(draft_path.read_text(encoding="utf-8"))
    payload["content_md"] = "空白文本"
    payload["summary"] = "空白摘要"
    payload["updated_at"] = "2026-03-12T12:00:00+00:00"
    draft_path.write_text(__import__("json").dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    rechecked = client.post(f"/api/projects/{project['project_id']}/drafts/{draft['draft_id']}/checks/recheck")
    assert rechecked.status_code == 200
    assert rechecked.json()["report"]["overall_status"] == "blocked"

    fetched = client.get(f"/api/projects/{project['project_id']}/drafts/{draft['draft_id']}")
    assert fetched.status_code == 200
    assert fetched.json()["draft"]["latest_check_run_id"] != old_run_id
    assert fetched.json()["draft"]["last_check_status"] == "blocked"
    assert fetched.json()["draft"]["last_check_blocker_count"] > 0



def test_blocker_draft_accept_returns_409(client: TestClient, build_ready_scene_project) -> None:
    project = build_ready_scene_project(confirm_scene=True)
    generated = client.post(
        f"/api/projects/{project['project_id']}/drafts/scenes/{project['scene_id']}/generate",
        json={"mode": "outline_strict"},
    )
    draft = generated.json()["draft"]

    draft_path = _project_root(project["slug"]) / draft["draft_path"]
    payload = __import__("json").loads(draft_path.read_text(encoding="utf-8"))
    payload["content_md"] = "空白文本"
    payload["summary"] = "空白摘要"
    payload["updated_at"] = "2026-03-12T12:00:00+00:00"
    draft_path.write_text(__import__("json").dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    response = client.post(f"/api/projects/{project['project_id']}/drafts/{draft['draft_id']}/accept")
    assert response.status_code == 409



def test_warning_only_draft_accept_returns_200(client: TestClient, build_ready_scene_project) -> None:
    project = build_ready_scene_project(confirm_scene=True)
    generated = client.post(
        f"/api/projects/{project['project_id']}/drafts/scenes/{project['scene_id']}/generate",
        json={"mode": "outline_strict"},
    )
    draft = generated.json()["draft"]

    draft_path = _project_root(project["slug"]) / draft["draft_path"]
    payload = __import__("json").loads(draft_path.read_text(encoding="utf-8"))
    obstacle = "反派打压"
    payload["content_md"] = payload["content_md"].replace(f"阻碍：{obstacle}", "阻碍：")
    payload["content_md"] = payload["content_md"].replace(f"先遭遇“{obstacle}”", "先遭遇“”")
    payload["summary"] = payload["summary"].replace(obstacle, "")
    payload["updated_at"] = "2026-03-12T12:00:00+00:00"
    draft_path.write_text(__import__("json").dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    response = client.post(f"/api/projects/{project['project_id']}/drafts/{draft['draft_id']}/accept")
    assert response.status_code == 200
    assert response.json()["draft"]["status"] == "accepted"



def test_missing_report_on_accept_triggers_preflight_rerun(client: TestClient, build_ready_scene_project) -> None:
    project = build_ready_scene_project(confirm_scene=True)
    generated = client.post(
        f"/api/projects/{project['project_id']}/drafts/scenes/{project['scene_id']}/generate",
        json={"mode": "outline_strict"},
    )
    draft = generated.json()["draft"]
    old_run_id = draft["latest_check_run_id"]
    report_path = _project_root(project["slug"]) / draft["latest_check_report_path"]
    report_path.unlink()

    accepted = client.post(f"/api/projects/{project['project_id']}/drafts/{draft['draft_id']}/accept")
    assert accepted.status_code == 200
    assert accepted.json()["draft"]["latest_check_run_id"] != old_run_id



def test_scene_studio_page_is_available(client: TestClient) -> None:
    response = client.get("/studio/scene.html")
    assert response.status_code == 200
    assert "Repair Draft" in response.text


def test_generate_and_repair_include_style_constraints(client: TestClient, build_ready_scene_project) -> None:
    import json

    project = build_ready_scene_project(confirm_scene=True)
    voice_profile_path = _project_root(project["slug"]) / "bible" / "voice_profile.json"
    voice_profile_path.write_text(
        json.dumps(
            {
                "project_id": project["project_id"],
                "version": 1,
                "updated_at": "2026-03-13T00:00:00Z",
                "enabled": True,
                "profile_name": "风格测试",
                "global_constraints": {
                    "sentence_rhythm": {
                        "baseline": "short",
                        "soft_max_sentence_chars": 20,
                        "burst_short_lines": True,
                    },
                    "paragraph_rhythm": {
                        "preferred_min_sentences": 1,
                        "preferred_max_sentences": 2,
                        "soft_max_sentences": 3,
                    },
                    "banned_phrases": ["按提纲推进"],
                    "narrative_habits": {
                        "narration_person": "third_limited",
                        "exposition_density": "low",
                        "inner_monologue_density": "low",
                        "dialogue_tag_style": "simple",
                    },
                    "payoff_style": {
                        "intensity": "direct",
                        "prefer_action_before_reaction": True,
                        "prefer_concrete_gain": True,
                        "avoid_empty_hype": True,
                    },
                },
                "character_voice_profiles": [],
                "notes": "",
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    generated = client.post(
        f"/api/projects/{project['project_id']}/drafts/scenes/{project['scene_id']}/generate",
        json={"mode": "outline_strict"},
    )
    assert generated.status_code == 201
    assert generated.json()["context_bundle"]["style_constraints"]["enabled"] is True
    assert "按提纲推进" not in generated.json()["draft"]["content_md"]

    draft_id = generated.json()["draft"]["draft_id"]
    draft_path = _project_root(project["slug"]) / generated.json()["draft"]["draft_path"]
    payload = json.loads(draft_path.read_text(encoding="utf-8"))
    payload["content_md"] = "空白文本。"
    payload["summary"] = "空白摘要。"
    payload["updated_at"] = "2026-03-12T12:00:00+00:00"
    draft_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    repaired = client.post(f"/api/projects/{project['project_id']}/drafts/{draft_id}/repair")
    assert repaired.status_code == 200
    assert repaired.json()["context_bundle"]["style_constraints"]["enabled"] is True


def test_generate_degrades_when_voice_profile_file_is_corrupt(client: TestClient, build_ready_scene_project) -> None:
    project = build_ready_scene_project(confirm_scene=True)
    voice_profile_path = _project_root(project["slug"]) / "bible" / "voice_profile.json"
    voice_profile_path.write_text("{broken json", encoding="utf-8")

    generated = client.post(
        f"/api/projects/{project['project_id']}/drafts/scenes/{project['scene_id']}/generate",
        json={"mode": "outline_strict"},
    )
    assert generated.status_code == 201
    style_constraints = generated.json()["context_bundle"]["style_constraints"]
    assert style_constraints["enabled"] is False
    assert style_constraints["character_voice_briefs"] == []
    assert style_constraints["warnings"]

def test_accept_preflight_reruns_checks_after_memory_changes(client: TestClient, build_ready_scene_project) -> None:
    project = build_ready_scene_project(confirm_scene=True)
    second_scene_id = project["scene_ids"][1]
    assert client.post(f"/api/projects/{project['project_id']}/plans/scenes/{second_scene_id}/confirm").status_code == 200

    second_generated = client.post(
        f"/api/projects/{project['project_id']}/drafts/scenes/{second_scene_id}/generate",
        json={"mode": "outline_strict"},
    )
    assert second_generated.status_code == 201
    second_draft = second_generated.json()["draft"]
    old_run_id = second_draft["latest_check_run_id"]

    first_generated = client.post(
        f"/api/projects/{project['project_id']}/drafts/scenes/{project['scene_id']}/generate",
        json={"mode": "outline_strict"},
    )
    assert first_generated.status_code == 201
    first_draft_id = first_generated.json()["draft"]["draft_id"]
    assert client.post(f"/api/projects/{project['project_id']}/drafts/{first_draft_id}/accept").status_code == 200

    accepted = client.post(f"/api/projects/{project['project_id']}/drafts/{second_draft['draft_id']}/accept")
    assert accepted.status_code == 200
    assert accepted.json()["draft"]["latest_check_run_id"] != old_run_id


def test_corrupt_context_bundle_degrades_without_500(client: TestClient, build_ready_scene_project) -> None:
    project = build_ready_scene_project(confirm_scene=True)
    generated = client.post(
        f"/api/projects/{project['project_id']}/drafts/scenes/{project['scene_id']}/generate",
        json={"mode": "outline_strict"},
    )
    assert generated.status_code == 201
    draft = generated.json()["draft"]

    bundle_path = _project_root(project["slug"]) / draft["context_bundle_path"]
    bundle_path.write_text("{broken json", encoding="utf-8")

    fetched = client.get(f"/api/projects/{project['project_id']}/drafts/{draft['draft_id']}")
    assert fetched.status_code == 200
    assert fetched.json()["context_bundle"] is not None

    rejected = client.post(f"/api/projects/{project['project_id']}/drafts/{draft['draft_id']}/reject")
    assert rejected.status_code == 200
    assert rejected.json()["draft"]["status"] == "rejected"


def test_generate_and_repair_include_previous_volume_summary_when_previous_volume_is_finalized(
    client: TestClient,
    create_finalized_project,
) -> None:
    import json

    project = _create_two_volume_project(client, create_finalized_project)

    generated_one = client.post(
        f"/api/projects/{project['project_id']}/drafts/scenes/{project['scene_ids_two'][0]}/generate",
        json={"mode": "outline_strict"},
    )
    assert generated_one.status_code == 201
    previous_volume_one = generated_one.json()["context_bundle"]["retrieved_memory"]["previous_volume_summary"]
    assert previous_volume_one is not None
    assert previous_volume_one["selection_reason"] == "volume_boundary"

    generated_two = client.post(
        f"/api/projects/{project['project_id']}/drafts/scenes/{project['scene_ids_two'][1]}/generate",
        json={"mode": "outline_strict"},
    )
    assert generated_two.status_code == 201
    previous_volume_two = generated_two.json()["context_bundle"]["retrieved_memory"]["previous_volume_summary"]
    assert previous_volume_two is not None
    assert previous_volume_two["selection_reason"] == "early_volume_context"

    generated_three = client.post(
        f"/api/projects/{project['project_id']}/drafts/scenes/{project['scene_ids_two'][2]}/generate",
        json={"mode": "outline_strict"},
    )
    assert generated_three.status_code == 201
    assert generated_three.json()["context_bundle"]["retrieved_memory"]["previous_volume_summary"] is None

    source_draft = generated_one.json()["draft"]
    source_path = _project_root(project["slug"]) / source_draft["draft_path"]
    payload = json.loads(source_path.read_text(encoding="utf-8"))
    payload["content_md"] = "空白文本。"
    payload["summary"] = "空白摘要。"
    payload["updated_at"] = "2026-03-12T12:00:00+00:00"
    source_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    repaired = client.post(f"/api/projects/{project['project_id']}/drafts/{source_draft['draft_id']}/repair")
    assert repaired.status_code == 200
    repaired_previous_volume = repaired.json()["context_bundle"]["retrieved_memory"]["previous_volume_summary"]
    assert repaired_previous_volume is not None
    assert repaired_previous_volume["volume_id"] == project["volume_one_id"]


def test_generate_degrades_when_volume_summaries_are_missing_or_corrupt(
    client: TestClient,
    create_finalized_project,
) -> None:
    project = _create_two_volume_project(client, create_finalized_project)
    volume_summaries_path = _project_root(project["slug"]) / "memory" / "volume_summaries.json"

    volume_summaries_path.unlink()
    generated_missing = client.post(
        f"/api/projects/{project['project_id']}/drafts/scenes/{project['scene_ids_two'][0]}/generate",
        json={"mode": "outline_strict"},
    )
    assert generated_missing.status_code == 201
    retrieved_missing = generated_missing.json()["context_bundle"]["retrieved_memory"]
    assert retrieved_missing["previous_volume_summary"] is None
    assert "volume_summaries_unavailable" in retrieved_missing["warnings"]

    volume_summaries_path.write_text("{broken json", encoding="utf-8")
    generated_broken = client.post(
        f"/api/projects/{project['project_id']}/drafts/scenes/{project['scene_ids_two'][0]}/generate",
        json={"mode": "outline_strict"},
    )
    assert generated_broken.status_code == 201
    retrieved_broken = generated_broken.json()["context_bundle"]["retrieved_memory"]
    assert retrieved_broken["previous_volume_summary"] is None
    assert "volume_summaries_unavailable" in retrieved_broken["warnings"]


def test_repair_endpoint_handles_blocked_and_warning_drafts(client: TestClient, build_ready_scene_project) -> None:
    project = build_ready_scene_project(confirm_scene=True)
    generated = client.post(
        f"/api/projects/{project['project_id']}/drafts/scenes/{project['scene_id']}/generate",
        json={"mode": "outline_strict"},
    )
    assert generated.status_code == 201
    source = generated.json()["draft"]

    source_path = _project_root(project["slug"]) / source["draft_path"]
    payload = __import__("json").loads(source_path.read_text(encoding="utf-8"))
    payload["content_md"] = "空白文本"
    payload["summary"] = "空白摘要"
    payload["updated_at"] = "2026-03-12T12:00:00+00:00"
    source_path.write_text(__import__("json").dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    repaired = client.post(f"/api/projects/{project['project_id']}/drafts/{source['draft_id']}/repair")
    assert repaired.status_code == 200
    repaired_payload = repaired.json()
    assert repaired_payload["draft"]["operation"] == "repair"
    assert repaired_payload["draft"]["supersedes_draft_id"] == source["draft_id"]
    assert repaired_payload["draft"]["latest_check_report_path"] != source["latest_check_report_path"]

    source_fetched = client.get(f"/api/projects/{project['project_id']}/drafts/{source['draft_id']}")
    assert source_fetched.status_code == 200
    assert source_fetched.json()["draft"]["status"] == "superseded"

    scene_payload = client.get(f"/api/projects/{project['project_id']}/plans/scenes/{project['scene_id']}").json()
    scene_plan_path = _project_root(project["slug"]) / f"plans/scenes/chapter-{scene_payload['chapter_no']:04d}-scene-{scene_payload['scene_no']:03d}.json"
    scene_plan = __import__("json").loads(scene_plan_path.read_text(encoding="utf-8"))
    scene_plan["time_anchor"] = "黎明前"
    scene_plan["version"] = scene_plan["version"] + 1
    scene_plan_path.write_text(__import__("json").dumps(scene_plan, ensure_ascii=False, indent=2), encoding="utf-8")

    warning_generated = client.post(
        f"/api/projects/{project['project_id']}/drafts/scenes/{project['scene_id']}/generate",
        json={"mode": "momentum"},
    )
    warning_payload_root = warning_generated.json()
    warning_source = warning_payload_root["draft"]
    assert warning_payload_root["check_report"]["overall_status"] == "warning"

    repaired_warning = client.post(f"/api/projects/{project['project_id']}/drafts/{warning_source['draft_id']}/repair")
    assert repaired_warning.status_code == 200
    assert repaired_warning.json()["draft"]["operation"] == "repair"


def test_repair_endpoint_rejects_clean_sources_and_preserves_manifest_on_failure(
    client: TestClient,
    build_ready_scene_project,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from backend.app.api import drafts as drafts_api
    from backend.app.services.exceptions import ConflictError

    project = build_ready_scene_project(confirm_scene=True)
    generated = client.post(
        f"/api/projects/{project['project_id']}/drafts/scenes/{project['scene_id']}/generate",
        json={"mode": "outline_strict"},
    )
    assert generated.status_code == 201
    source = generated.json()["draft"]

    clean_response = client.post(f"/api/projects/{project['project_id']}/drafts/{source['draft_id']}/repair")
    assert clean_response.status_code == 409

    manifest_before = client.get(f"/api/projects/{project['project_id']}/drafts/scenes/{project['scene_id']}").json()

    source_path = _project_root(project["slug"]) / source["draft_path"]
    payload = __import__("json").loads(source_path.read_text(encoding="utf-8"))
    payload["content_md"] = "空白文本"
    payload["summary"] = "空白摘要"
    payload["updated_at"] = "2026-03-12T12:00:00+00:00"
    source_path.write_text(__import__("json").dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    original_builder = drafts_api._build_services

    def _patched(settings):
        draft_service, checks_service, repair_service = original_builder(settings)

        def _boom(*args, **kwargs):
            raise ConflictError("repair failed")

        repair_service.repair_draft = _boom
        return draft_service, checks_service, repair_service

    monkeypatch.setattr(drafts_api, "_build_services", _patched)
    failed = client.post(f"/api/projects/{project['project_id']}/drafts/{source['draft_id']}/repair")
    assert failed.status_code == 409
    manifest_after = client.get(f"/api/projects/{project['project_id']}/drafts/scenes/{project['scene_id']}").json()
    assert manifest_after == manifest_before




