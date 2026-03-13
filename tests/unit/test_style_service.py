from __future__ import annotations

import json


def _build_style_service(seeded):
    from backend.app.services.style_service import StyleService

    return StyleService(seeded["paths"], seeded["file_repository"], seeded["sqlite_repository"])


def test_corrupt_voice_profile_loads_disabled_profile_with_warnings(service_container) -> None:
    seeded = service_container["seed_project"](ready_scene=True, scene_count_hint=2)
    manifest = seeded["manifest"]
    paths = seeded["paths"]
    file_repository = seeded["file_repository"]
    style_service = _build_style_service(seeded)

    voice_profile_path = paths.voice_profile_path(manifest.slug)
    file_repository.write_text(voice_profile_path, "{broken json")

    result = style_service.get_voice_profile(manifest.project_id)

    assert result.profile.enabled is False
    assert result.profile.project_id == manifest.project_id
    assert result.warnings
    assert result.profile.global_constraints.banned_phrases == []
    assert result.profile.character_voice_profiles == []


def test_sanitizer_is_deterministic_idempotent_and_preserves_protected_phrases(service_container) -> None:
    seeded = service_container["seed_project"](ready_scene=True, scene_count_hint=2)
    manifest = seeded["manifest"]
    style_service = _build_style_service(seeded)

    style_service.put_voice_profile(
        manifest.project_id,
        {
            "project_id": manifest.project_id,
            "version": 1,
            "updated_at": "2026-03-13T00:00:00Z",
            "enabled": True,
            "profile_name": "测试风格",
            "global_constraints": {
                "sentence_rhythm": {
                    "baseline": "short",
                    "soft_max_sentence_chars": 20,
                    "burst_short_lines": True,
                },
                "paragraph_rhythm": {
                    "preferred_min_sentences": 1,
                    "preferred_max_sentences": 2,
                    "soft_max_sentences": 2,
                },
                "banned_phrases": ["空气都安静了", "主角爆发"],
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
            "character_voice_profiles": [
                {
                    "character_id": "char_mc",
                    "speech_style_tag": "short_cold_direct",
                    "sentence_length_bias": "short",
                    "preferred_terms": ["行"],
                    "forbidden_terms": ["老子无敌"],
                    "address_terms": ["你"],
                }
            ],
            "notes": "",
        },
    )
    load_result = style_service.get_voice_profile(manifest.project_id)

    content = "主角爆发。空气都安静了。顾望安说老子无敌。地点：云海市。"
    summary = "主角爆发，空气都安静了。"
    protected = {"主角爆发", "顾望安", "云海市"}

    first_content, first_summary = style_service.sanitize_text(
        content,
        summary,
        load_result.profile.to_disabled_or_enabled_bundle(character_ids=["char_mc"]),
        protected_phrases=protected,
    )
    second_content, second_summary = style_service.sanitize_text(
        first_content,
        first_summary,
        load_result.profile.to_disabled_or_enabled_bundle(character_ids=["char_mc"]),
        protected_phrases=protected,
    )

    assert first_content == second_content
    assert first_summary == second_summary
    assert "空气都安静了" not in first_content
    assert "老子无敌" not in first_content
    assert "主角爆发" in first_content
    assert "顾望安" in first_content
    assert "云海市" in first_content

