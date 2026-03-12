from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from backend.app.domain.models.project import CharacterCard, CharacterDocument, PowerSystemDocument, StoryBible, WorldDocument


class BibleAggregateResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    story_bible: StoryBible
    characters: CharacterDocument
    world: WorldDocument
    power_system: PowerSystemDocument
    aggregate_status: str


class StoryBibleWriteRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str | None = None
    genre: str | None = None
    subgenres: list[str] | None = None
    target_audience: list[str] | None = None
    logline: str | None = None
    premise: str | None = None
    themes: list[str] | None = None
    selling_points: list[str] | None = None
    core_conflicts: list[str] | None = None
    story_promise: str | None = None
    narrative_constraints: list[str] | None = None
    protagonist_ids: list[str] | None = None
    featured_faction_ids: list[str] | None = None
    featured_location_ids: list[str] | None = None
    world_hook: str | None = None
    power_hook: str | None = None


class WorldWriteRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    setting_era: str | None = None
    setting_scope: str | None = None
    tone: str | None = None
    world_rules: list[dict[str, Any]] | None = None
    factions: list[dict[str, Any]] | None = None
    locations: list[dict[str, Any]] | None = None
    timeline_baseline: dict[str, Any] | None = None


class PowerSystemWriteRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    system_name: str | None = None
    source_type: str | None = None
    core_rules: list[str] | None = None
    realm_ladder: list[dict[str, Any]] | None = None
    resources: list[dict[str, Any]] | None = None
    costs: list[str] | None = None
    taboos: list[str] | None = None
    upgrade_rhythm_guideline: str | None = None


class CharacterCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1)
    role: str = Field(min_length=1)
    is_protagonist: bool = False
    aliases: list[str] = Field(default_factory=list)
    archetype: str = ""
    core_desire: str = ""
    core_fear: str = ""
    secret: str = ""
    realm_level: str = ""
    traits: list[str] = Field(default_factory=list)
    public_goal: str = ""
    private_goal: str = ""
    faction_id: str | None = None
    first_appearance_hint: str = ""
    relationships: list[dict[str, Any]] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class CharacterUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = None
    role: str | None = None
    is_protagonist: bool | None = None
    aliases: list[str] | None = None
    archetype: str | None = None
    core_desire: str | None = None
    core_fear: str | None = None
    secret: str | None = None
    realm_level: str | None = None
    traits: list[str] | None = None
    public_goal: str | None = None
    private_goal: str | None = None
    faction_id: str | None = None
    first_appearance_hint: str | None = None
    relationships: list[dict[str, Any]] | None = None
    notes: list[str] | None = None


class BibleInitializationResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    story_bible: StoryBible
    characters: CharacterDocument
    world: WorldDocument
    power_system: PowerSystemDocument
    aggregate_status: str


class CharacterResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    item: CharacterCard
