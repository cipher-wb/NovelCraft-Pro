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
    logline: str = ""
    premise: str = ""
    themes: list[str] = Field(default_factory=list)
    world_rules: list[dict[str, Any]] = Field(default_factory=list)
    power_system: dict[str, Any] = Field(default_factory=dict)
    factions: list[dict[str, Any]] = Field(default_factory=list)
    locations: list[dict[str, Any]] = Field(default_factory=list)
    protagonist_ids: list[str] = Field(default_factory=list)
    voice_profile: dict[str, Any] = Field(default_factory=dict)
    version: int = 1
    updated_at: datetime


class CharacterCard(DomainModel):
    character_id: str
    project_id: str
    name: str
    aliases: list[str] = Field(default_factory=list)
    role: str
    archetype: str = ""
    core_desire: str = ""
    core_fear: str = ""
    secret: str = ""
    realm_level: str = ""
    traits: list[str] = Field(default_factory=list)
    relationships: list[dict[str, Any]] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)
    version: int = 1
