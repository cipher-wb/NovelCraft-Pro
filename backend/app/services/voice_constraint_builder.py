from __future__ import annotations

from backend.app.domain.models.style import CharacterVoiceBrief, StyleConstraintBundle
from backend.app.services.style_service import StyleService


class VoiceConstraintBuilder:
    def __init__(self, style_service: StyleService) -> None:
        self.style_service = style_service

    def build(self, project_id: str, scene_character_ids: list[str]) -> StyleConstraintBundle:
        load_result = self.style_service.get_voice_profile(project_id)
        profile = load_result.profile
        if not profile.enabled:
            return self.style_service.disabled_bundle(load_result.warnings)

        wanted_ids = set(scene_character_ids)
        briefs = [
            CharacterVoiceBrief(
                character_id=item.character_id,
                speech_style_tag=item.speech_style_tag,
                sentence_length_bias=item.sentence_length_bias,
                preferred_terms=item.preferred_terms,
                forbidden_terms=item.forbidden_terms,
                address_terms=item.address_terms,
            )
            for item in profile.character_voice_profiles
            if item.character_id in wanted_ids
        ]
        return StyleConstraintBundle(
            enabled=True,
            profile_name=profile.profile_name,
            global_constraints={
                "sentence_rhythm": {
                    "baseline": profile.global_constraints.sentence_rhythm.baseline,
                    "soft_max_sentence_chars": profile.global_constraints.sentence_rhythm.soft_max_sentence_chars,
                    "burst_short_lines": profile.global_constraints.sentence_rhythm.burst_short_lines,
                },
                "paragraph_rhythm": {
                    "preferred_min_sentences": profile.global_constraints.paragraph_rhythm.preferred_min_sentences,
                    "preferred_max_sentences": profile.global_constraints.paragraph_rhythm.preferred_max_sentences,
                    "soft_max_sentences": profile.global_constraints.paragraph_rhythm.soft_max_sentences,
                },
                "banned_phrases": profile.global_constraints.banned_phrases,
                "narrative_habits": {
                    "narration_person": profile.global_constraints.narrative_habits.narration_person,
                    "exposition_density": profile.global_constraints.narrative_habits.exposition_density,
                    "inner_monologue_density": profile.global_constraints.narrative_habits.inner_monologue_density,
                    "dialogue_tag_style": profile.global_constraints.narrative_habits.dialogue_tag_style,
                },
                "payoff_style": {
                    "intensity": profile.global_constraints.payoff_style.intensity,
                    "prefer_action_before_reaction": profile.global_constraints.payoff_style.prefer_action_before_reaction,
                    "prefer_concrete_gain": profile.global_constraints.payoff_style.prefer_concrete_gain,
                    "avoid_empty_hype": profile.global_constraints.payoff_style.avoid_empty_hype,
                },
            },
            character_voice_briefs=briefs,
            warnings=load_result.warnings,
        )

