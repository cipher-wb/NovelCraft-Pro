from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import Field

from backend.app.domain.models.common import DomainModel, utc_now


class VoiceSentenceRhythm(DomainModel):
    baseline: Literal["short", "medium_short", "medium"] = "medium_short"
    soft_max_sentence_chars: int = 40
    burst_short_lines: bool = False


class VoiceParagraphRhythm(DomainModel):
    preferred_min_sentences: int = 1
    preferred_max_sentences: int = 3
    soft_max_sentences: int = 4


class VoiceNarrativeHabits(DomainModel):
    narration_person: Literal["third_limited", "first_person"] = "third_limited"
    exposition_density: Literal["low", "medium"] = "low"
    inner_monologue_density: Literal["low", "medium"] = "low"
    dialogue_tag_style: Literal["simple", "explicit"] = "simple"


class VoicePayoffStyle(DomainModel):
    intensity: Literal["direct", "restrained"] = "direct"
    prefer_action_before_reaction: bool = True
    prefer_concrete_gain: bool = True
    avoid_empty_hype: bool = True


class VoiceGlobalConstraints(DomainModel):
    sentence_rhythm: VoiceSentenceRhythm = Field(default_factory=VoiceSentenceRhythm)
    paragraph_rhythm: VoiceParagraphRhythm = Field(default_factory=VoiceParagraphRhythm)
    banned_phrases: list[str] = Field(default_factory=list)
    narrative_habits: VoiceNarrativeHabits = Field(default_factory=VoiceNarrativeHabits)
    payoff_style: VoicePayoffStyle = Field(default_factory=VoicePayoffStyle)


class CharacterVoiceProfile(DomainModel):
    character_id: str
    speech_style_tag: str
    sentence_length_bias: Literal["short", "medium", "mixed"]
    preferred_terms: list[str] = Field(default_factory=list)
    forbidden_terms: list[str] = Field(default_factory=list)
    address_terms: list[str] = Field(default_factory=list)


class VoiceProfileDocument(DomainModel):
    project_id: str
    version: int = 1
    updated_at: datetime = Field(default_factory=utc_now)
    enabled: bool = False
    profile_name: str = ""
    global_constraints: VoiceGlobalConstraints = Field(default_factory=VoiceGlobalConstraints)
    character_voice_profiles: list[CharacterVoiceProfile] = Field(default_factory=list)
    notes: str = ""

    def to_disabled_or_enabled_bundle(
        self,
        character_ids: list[str],
        warnings: list[str] | None = None,
    ) -> "StyleConstraintBundle":
        if not self.enabled:
            return StyleConstraintBundle(
                enabled=False,
                profile_name="",
                global_constraints=StyleGlobalConstraintsBundle(),
                character_voice_briefs=[],
                warnings=list(warnings or []),
            )
        wanted = set(character_ids)
        return StyleConstraintBundle(
            enabled=True,
            profile_name=self.profile_name,
            global_constraints=StyleGlobalConstraintsBundle(
                sentence_rhythm=StyleSentenceRhythmBundle(
                    baseline=self.global_constraints.sentence_rhythm.baseline,
                    soft_max_sentence_chars=self.global_constraints.sentence_rhythm.soft_max_sentence_chars,
                    burst_short_lines=self.global_constraints.sentence_rhythm.burst_short_lines,
                ),
                paragraph_rhythm=StyleParagraphRhythmBundle(
                    preferred_min_sentences=self.global_constraints.paragraph_rhythm.preferred_min_sentences,
                    preferred_max_sentences=self.global_constraints.paragraph_rhythm.preferred_max_sentences,
                    soft_max_sentences=self.global_constraints.paragraph_rhythm.soft_max_sentences,
                ),
                banned_phrases=self.global_constraints.banned_phrases,
                narrative_habits=StyleNarrativeHabitsBundle(
                    narration_person=self.global_constraints.narrative_habits.narration_person,
                    exposition_density=self.global_constraints.narrative_habits.exposition_density,
                    inner_monologue_density=self.global_constraints.narrative_habits.inner_monologue_density,
                    dialogue_tag_style=self.global_constraints.narrative_habits.dialogue_tag_style,
                ),
                payoff_style=StylePayoffStyleBundle(
                    intensity=self.global_constraints.payoff_style.intensity,
                    prefer_action_before_reaction=self.global_constraints.payoff_style.prefer_action_before_reaction,
                    prefer_concrete_gain=self.global_constraints.payoff_style.prefer_concrete_gain,
                    avoid_empty_hype=self.global_constraints.payoff_style.avoid_empty_hype,
                ),
            ),
            character_voice_briefs=[
                CharacterVoiceBrief(
                    character_id=item.character_id,
                    speech_style_tag=item.speech_style_tag,
                    sentence_length_bias=item.sentence_length_bias,
                    preferred_terms=item.preferred_terms,
                    forbidden_terms=item.forbidden_terms,
                    address_terms=item.address_terms,
                )
                for item in self.character_voice_profiles
                if item.character_id in wanted
            ],
            warnings=list(warnings or []),
        )


class StyleSentenceRhythmBundle(DomainModel):
    baseline: str = ""
    soft_max_sentence_chars: int = 0
    burst_short_lines: bool = False


class StyleParagraphRhythmBundle(DomainModel):
    preferred_min_sentences: int = 0
    preferred_max_sentences: int = 0
    soft_max_sentences: int = 0


class StyleNarrativeHabitsBundle(DomainModel):
    narration_person: str = ""
    exposition_density: str = ""
    inner_monologue_density: str = ""
    dialogue_tag_style: str = ""


class StylePayoffStyleBundle(DomainModel):
    intensity: str = ""
    prefer_action_before_reaction: bool = False
    prefer_concrete_gain: bool = False
    avoid_empty_hype: bool = False


class StyleGlobalConstraintsBundle(DomainModel):
    sentence_rhythm: StyleSentenceRhythmBundle = Field(default_factory=StyleSentenceRhythmBundle)
    paragraph_rhythm: StyleParagraphRhythmBundle = Field(default_factory=StyleParagraphRhythmBundle)
    banned_phrases: list[str] = Field(default_factory=list)
    narrative_habits: StyleNarrativeHabitsBundle = Field(default_factory=StyleNarrativeHabitsBundle)
    payoff_style: StylePayoffStyleBundle = Field(default_factory=StylePayoffStyleBundle)


class CharacterVoiceBrief(DomainModel):
    character_id: str
    speech_style_tag: str = ""
    sentence_length_bias: str = ""
    preferred_terms: list[str] = Field(default_factory=list)
    forbidden_terms: list[str] = Field(default_factory=list)
    address_terms: list[str] = Field(default_factory=list)


class StyleConstraintBundle(DomainModel):
    enabled: bool = False
    profile_name: str = ""
    global_constraints: StyleGlobalConstraintsBundle = Field(default_factory=StyleGlobalConstraintsBundle)
    character_voice_briefs: list[CharacterVoiceBrief] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class VoiceProfileReadResult(DomainModel):
    profile: VoiceProfileDocument
    warnings: list[str] = Field(default_factory=list)
