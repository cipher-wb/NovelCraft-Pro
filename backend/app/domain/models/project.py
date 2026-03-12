from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import Field

from backend.app.domain.models.common import DomainModel


class ProjectManifest(DomainModel):
    project_id: str
    slug: str
    title: str
    genre: str
    status: str
    target_chapters: int
    target_words: int
    active_volume_no: int = 1
    active_chapter_no: int = 1
    created_at: datetime
    updated_at: datetime


class ConsultantDossier(DomainModel):
    dossier_id: str
    project_id: str
    high_concept: str
    subgenres: list[str] = Field(default_factory=list)
    target_audience: list[str] = Field(default_factory=list)
    selling_points: list[str] = Field(default_factory=list)
    protagonist_seed: dict[str, Any] = Field(default_factory=dict)
    golden_finger: dict[str, Any] = Field(default_factory=dict)
    core_conflicts: list[str] = Field(default_factory=list)
    chapter_1_30_beats: list[dict[str, Any]] = Field(default_factory=list)
    qa_transcript: list[dict[str, Any]] = Field(default_factory=list)
    version: int = 1


class StoryBible(DomainModel):
    bible_id: str
    project_id: str
    source_dossier_id: str | None = None
    title: str = ""
    genre: str = ""
    subgenres: list[str] = Field(default_factory=list)
    target_audience: list[str] = Field(default_factory=list)
    logline: str = ""
    premise: str = ""
    themes: list[str] = Field(default_factory=list)
    selling_points: list[str] = Field(default_factory=list)
    core_conflicts: list[str] = Field(default_factory=list)
    story_promise: str = ""
    narrative_constraints: list[str] = Field(default_factory=list)
    protagonist_ids: list[str] = Field(default_factory=list)
    featured_faction_ids: list[str] = Field(default_factory=list)
    featured_location_ids: list[str] = Field(default_factory=list)
    world_hook: str = ""
    power_hook: str = ""
    status: str = "draft"
    version: int = 1
    updated_at: datetime


class CharacterRelationship(DomainModel):
    target_character_id: str
    relation_type: str
    summary: str = ""


class CharacterCard(DomainModel):
    character_id: str
    project_id: str
    name: str
    aliases: list[str] = Field(default_factory=list)
    role: str
    is_protagonist: bool = False
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
    relationships: list[CharacterRelationship] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)
    status: str = "draft"
    version: int = 1


class CharacterDocument(DomainModel):
    project_id: str
    status: str = "draft"
    version: int = 1
    updated_at: datetime
    items: list[CharacterCard] = Field(default_factory=list)


class WorldRule(DomainModel):
    rule_id: str
    title: str
    content: str
    hardness: str = "hard"
    exceptions: list[str] = Field(default_factory=list)
    visibility: str = "hidden"


class Faction(DomainModel):
    faction_id: str
    name: str
    type: str = ""
    goal: str = ""
    resources: list[str] = Field(default_factory=list)
    public_image: str = ""
    key_member_ids: list[str] = Field(default_factory=list)
    status: str = "active"


class Location(DomainModel):
    location_id: str
    name: str
    type: str = ""
    description: str = ""
    parent_location_id: str | None = None
    owner_faction_id: str | None = None
    tags: list[str] = Field(default_factory=list)


class WorldDocument(DomainModel):
    project_id: str
    status: str = "draft"
    version: int = 1
    updated_at: datetime
    setting_era: str = ""
    setting_scope: str = ""
    tone: str = ""
    world_rules: list[WorldRule] = Field(default_factory=list)
    factions: list[Faction] = Field(default_factory=list)
    locations: list[Location] = Field(default_factory=list)
    timeline_baseline: dict[str, Any] = Field(default_factory=dict)


class RealmLevel(DomainModel):
    level_id: str
    name: str
    order: int
    requirements: list[str] = Field(default_factory=list)
    benefits: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)


class PowerResource(DomainModel):
    resource_id: str
    name: str
    purpose: str = ""
    rarity: str = ""
    constraints: list[str] = Field(default_factory=list)


class PowerSystemDocument(DomainModel):
    project_id: str
    status: str = "draft"
    version: int = 1
    updated_at: datetime
    system_name: str = ""
    source_type: str = ""
    core_rules: list[str] = Field(default_factory=list)
    realm_ladder: list[RealmLevel] = Field(default_factory=list)
    resources: list[PowerResource] = Field(default_factory=list)
    costs: list[str] = Field(default_factory=list)
    taboos: list[str] = Field(default_factory=list)
    upgrade_rhythm_guideline: str = ""
