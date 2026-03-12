from __future__ import annotations

from datetime import datetime

from pydantic import AliasChoices, Field

from backend.app.domain.models.common import DomainModel


class OutlineVolumeRef(DomainModel):
    volume_id: str
    volume_no: int
    title: str
    summary: str = ""
    goal: str = ""
    planned_chapters: int = 0
    status: str = "draft"
    file_path: str


class MasterOutlineDocument(DomainModel):
    project_id: str
    outline_status: str = Field(default="draft", validation_alias=AliasChoices("outline_status", "status"))
    version: int = 1
    updated_at: datetime
    source_bible_version: int = 0
    total_volumes: int = 0
    active_volume_id: str | None = None
    volumes: list[OutlineVolumeRef] = Field(default_factory=list)


class VolumePlan(DomainModel):
    volume_id: str
    project_id: str
    volume_no: int
    title: str
    summary: str = ""
    goal: str = ""
    core_conflict: str = ""
    opening_hook: str = ""
    closing_hook: str = ""
    upgrade_target: str = ""
    entry_state: list[str] = Field(default_factory=list)
    exit_state: list[str] = Field(default_factory=list)
    major_beats: list[str] = Field(default_factory=list)
    planned_chapters: int = 0
    chapter_ids: list[str] = Field(default_factory=list)
    source_bible_version: int = 0
    status: str = "draft"
    version: int = 1
    stale_reason: str | None = None


class ChapterPlan(DomainModel):
    chapter_id: str
    project_id: str
    volume_id: str
    volume_no: int
    chapter_no: int
    title: str
    summary: str = ""
    purpose: str = ""
    main_conflict: str = ""
    hook: str = ""
    entry_state: list[str] = Field(default_factory=list)
    exit_state: list[str] = Field(default_factory=list)
    character_ids: list[str] = Field(default_factory=list)
    faction_ids: list[str] = Field(default_factory=list)
    foreshadow_ids: list[str] = Field(default_factory=list)
    payoff_ids: list[str] = Field(default_factory=list)
    target_words: int = 0
    scene_ids: list[str] = Field(default_factory=list)
    source_volume_version: int = 0
    status: str = "draft"
    version: int = 1
    stale_reason: str | None = None


class ScenePlan(DomainModel):
    scene_id: str
    project_id: str
    volume_id: str
    chapter_id: str
    chapter_no: int
    scene_no: int
    title: str
    summary: str = ""
    scene_type: str = ""
    goal: str = ""
    obstacle: str = ""
    turning_point: str = ""
    outcome: str = ""
    location_id: str | None = None
    time_anchor: str = ""
    character_ids: list[str] = Field(default_factory=list)
    must_include: list[str] = Field(default_factory=list)
    forbidden: list[str] = Field(default_factory=list)
    target_words: int = 0
    emotional_beat: str = ""
    continuity_notes: str = ""
    source_chapter_version: int = 0
    status: str = "draft"
    version: int = 1
    stale_reason: str | None = None
