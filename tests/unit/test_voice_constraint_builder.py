from __future__ import annotations


def _build_builder(seeded):
    from backend.app.services.style_service import StyleService
    from backend.app.services.voice_constraint_builder import VoiceConstraintBuilder

    style_service = StyleService(seeded["paths"], seeded["file_repository"], seeded["sqlite_repository"])
    return style_service, VoiceConstraintBuilder(style_service)


def test_voice_constraint_builder_returns_fixed_disabled_shape(service_container) -> None:
    seeded = service_container["seed_project"](ready_scene=True, scene_count_hint=2)
    manifest = seeded["manifest"]
    paths = seeded["paths"]
    file_repository = seeded["file_repository"]
    style_service, builder = _build_builder(seeded)

    file_repository.write_text(paths.voice_profile_path(manifest.slug), "{broken json")
    bundle = builder.build(manifest.project_id, ["char_mc"])

    assert bundle.enabled is False
    assert bundle.profile_name == ""
    assert bundle.global_constraints.banned_phrases == []
    assert bundle.character_voice_briefs == []
    assert bundle.warnings


def test_voice_constraint_builder_only_keeps_current_scene_characters(service_container) -> None:
    seeded = service_container["seed_project"](ready_scene=True, scene_count_hint=2)
    manifest = seeded["manifest"]
    style_service, builder = _build_builder(seeded)

    style_service.put_voice_profile(
        manifest.project_id,
        {
            "project_id": manifest.project_id,
            "version": 1,
            "updated_at": "2026-03-13T00:00:00Z",
            "enabled": True,
            "profile_name": "角色风格",
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
            "character_voice_profiles": [
                {
                    "character_id": "char_mc",
                    "speech_style_tag": "short_cold_direct",
                    "sentence_length_bias": "short",
                    "preferred_terms": ["行"],
                    "forbidden_terms": ["废话"],
                    "address_terms": ["你"],
                },
                {
                    "character_id": "char_other",
                    "speech_style_tag": "support_soft",
                    "sentence_length_bias": "medium",
                    "preferred_terms": ["好"],
                    "forbidden_terms": ["滚"],
                    "address_terms": ["您"],
                },
            ],
            "notes": "",
        },
    )
    bundle = builder.build(manifest.project_id, ["char_mc"])

    assert bundle.enabled is True
    assert [item.character_id for item in bundle.character_voice_briefs] == ["char_mc"]

