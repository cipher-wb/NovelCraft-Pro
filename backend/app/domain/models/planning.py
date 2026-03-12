from __future__ import annotations

from pydantic import Field

from backend.app.domain.models.common import DomainModel


class VolumePlan(DomainModel):
    volume_id: str
    project_id: str
    volume_no: int
    title: str
    goal: str = ""
    core_conflict: str = ""
    opening_hook: str = ""
    closing_hook: str = ""
    upgrade_target: str = ""
    planned_chapters: int = 0
    status: str = "planned"
    summary: str = ""
    version: int = 1


class ChapterPlan(DomainModel):
    chapter_id: str
    project_id: str
    volume_id: str
    chapter_no: int
    title: str
    purpose: str = ""
    entry_state: list[str] = Field(default_factory=list)
    exit_state: list[str] = Field(default_factory=list)
    main_conflict: str = ""
    hook: str = ""
    participants: list[str] = Field(default_factory=list)
    foreshadow_ids: list[str] = Field(default_factory=list)
    payoff_ids: list[str] = Field(default_factory=list)
    target_words: int = 0
    status: str = "planned"
    version: int = 1


class ScenePlan(DomainModel):
    scene_id: str
    project_id: str
    chapter_id: str
    scene_no: int
    title: str
    scene_type: str = ""
    goal: str = ""
    obstacle: str = ""
    turning_point: str = ""
    outcome: str = ""
    location_id: str | None = None
    time_anchor: str = ""
    participants: list[str] = Field(default_factory=list)
    must_include: list[str] = Field(default_factory=list)
    forbidden: list[str] = Field(default_factory=list)
    target_words: int = 0
    status: str = "planned"
    version: int = 1
