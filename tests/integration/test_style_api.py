from __future__ import annotations

from pathlib import Path


def _voice_profile_path(slug: str) -> Path:
    return Path(__import__("os").environ["PROJECTS_ROOT"]) / slug / "bible" / "voice_profile.json"


def test_style_voice_profile_put_and_get_roundtrip(client, create_finalized_project) -> None:
    project = create_finalized_project()
    payload = {
        "project_id": project["project_id"],
        "version": 1,
        "updated_at": "2026-03-13T00:00:00Z",
        "enabled": True,
        "profile_name": "测试风格",
        "global_constraints": {
            "sentence_rhythm": {
                "baseline": "medium_short",
                "soft_max_sentence_chars": 40,
                "burst_short_lines": False,
            },
            "paragraph_rhythm": {
                "preferred_min_sentences": 1,
                "preferred_max_sentences": 3,
                "soft_max_sentences": 4,
            },
            "banned_phrases": ["空气都安静了"],
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
    }

    put_response = client.put(f"/api/projects/{project['project_id']}/style/voice-profile", json=payload)
    assert put_response.status_code == 200
    assert put_response.json()["profile"]["enabled"] is True

    get_response = client.get(f"/api/projects/{project['project_id']}/style/voice-profile")
    assert get_response.status_code == 200
    assert get_response.json()["profile"]["profile_name"] == "测试风格"
    assert get_response.json()["warnings"] == []


def test_style_voice_profile_put_invalid_returns_400_and_keeps_existing_file(client, create_finalized_project) -> None:
    project = create_finalized_project()
    valid_payload = {
        "project_id": project["project_id"],
        "version": 1,
        "updated_at": "2026-03-13T00:00:00Z",
        "enabled": True,
        "profile_name": "初始风格",
        "global_constraints": {
            "sentence_rhythm": {
                "baseline": "medium_short",
                "soft_max_sentence_chars": 40,
                "burst_short_lines": False,
            },
            "paragraph_rhythm": {
                "preferred_min_sentences": 1,
                "preferred_max_sentences": 3,
                "soft_max_sentences": 4,
            },
            "banned_phrases": [],
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
    }
    assert client.put(f"/api/projects/{project['project_id']}/style/voice-profile", json=valid_payload).status_code == 200
    before = _voice_profile_path(project["slug"]).read_text(encoding="utf-8")

    invalid_payload = {
        **valid_payload,
        "global_constraints": {
            **valid_payload["global_constraints"],
            "sentence_rhythm": {
                "baseline": "very_long",
                "soft_max_sentence_chars": 40,
                "burst_short_lines": False,
            },
        },
        "unknown_field": True,
    }
    response = client.put(f"/api/projects/{project['project_id']}/style/voice-profile", json=invalid_payload)
    assert response.status_code == 400
    after = _voice_profile_path(project["slug"]).read_text(encoding="utf-8")
    assert after == before


def test_style_voice_profile_get_returns_disabled_profile_when_file_is_corrupt(client, create_finalized_project) -> None:
    project = create_finalized_project()
    _voice_profile_path(project["slug"]).write_text("{broken json", encoding="utf-8")

    response = client.get(f"/api/projects/{project['project_id']}/style/voice-profile")
    assert response.status_code == 200
    payload = response.json()
    assert payload["profile"]["enabled"] is False
    assert payload["profile"]["global_constraints"]["banned_phrases"] == []
    assert payload["profile"]["character_voice_profiles"] == []
    assert payload["warnings"]

