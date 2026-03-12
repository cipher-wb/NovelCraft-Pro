from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict

from backend.app.domain.models.planning import ChapterPlan, MasterOutlineDocument, ScenePlan, VolumePlan


class VolumeWriteRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str | None = None
    summary: str | None = None
    goal: str | None = None
    core_conflict: str | None = None
    opening_hook: str | None = None
    closing_hook: str | None = None
    upgrade_target: str | None = None
    entry_state: list[str] | None = None
    exit_state: list[str] | None = None
    major_beats: list[str] | None = None
    planned_chapters: int | None = None
    chapter_ids: list[str] | None = None


class ChapterWriteRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str | None = None
    summary: str | None = None
    purpose: str | None = None
    main_conflict: str | None = None
    hook: str | None = None
    entry_state: list[str] | None = None
    exit_state: list[str] | None = None
    character_ids: list[str] | None = None
    faction_ids: list[str] | None = None
    foreshadow_ids: list[str] | None = None
    payoff_ids: list[str] | None = None
    target_words: int | None = None
    scene_ids: list[str] | None = None


class SceneWriteRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str | None = None
    summary: str | None = None
    scene_type: str | None = None
    goal: str | None = None
    obstacle: str | None = None
    turning_point: str | None = None
    outcome: str | None = None
    location_id: str | None = None
    time_anchor: str | None = None
    character_ids: list[str] | None = None
    must_include: list[str] | None = None
    forbidden: list[str] | None = None
    target_words: int | None = None
    emotional_beat: str | None = None
    continuity_notes: str | None = None


class VolumeListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[VolumePlan]


class ChapterListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[ChapterPlan]


class SceneListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[ScenePlan]


class MasterOutlineResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    outline: MasterOutlineDocument


class PlanGenerateOptions(BaseModel):
    model_config = ConfigDict(extra="forbid")

    overwrite: bool = False
    volume_count_hint: int | None = None
    chapters_per_volume_hint: int | None = None
    scene_count_hint: int | None = None
