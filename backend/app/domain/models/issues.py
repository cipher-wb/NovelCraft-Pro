from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import Field

from backend.app.domain.models.common import DomainModel


class ForeshadowItem(DomainModel):
    foreshadow_id: str
    project_id: str
    title: str
    category: str
    setup_text: str
    introduced_in_chapter_id: str
    introduced_in_scene_id: str | None = None
    expected_window: str = ""
    related_character_ids: list[str] = Field(default_factory=list)
    related_payoff_ids: list[str] = Field(default_factory=list)
    status: str = "open"
    resolved_in_chapter_id: str | None = None


class PayoffBeat(DomainModel):
    payoff_id: str
    project_id: str
    title: str
    payoff_type: str
    scope: str
    setup_ids: list[str] = Field(default_factory=list)
    target_window: str = ""
    intensity: int = 0
    reader_emotion_target: list[str] = Field(default_factory=list)
    status: str = "planned"
    delivery_chapter_id: str | None = None
    delivery_scene_id: str | None = None


class ConsistencyIssue(DomainModel):
    issue_id: str
    project_id: str
    issue_type: str
    rule_id: str
    severity: str
    status: str
    source_scope: str
    source_id: str
    title: str
    description: str
    evidence_refs: list[dict[str, Any]] = Field(default_factory=list)
    suggested_fix: list[str] = Field(default_factory=list)
    checker_run_id: str
    detected_at: datetime


class CheckSourceVersions(DomainModel):
    story_bible_version: int = 0
    characters_version: int = 0
    world_version: int = 0
    power_system_version: int = 0
    volume_version: int = 0
    chapter_version: int = 0
    scene_version: int = 0
    draft_updated_at: datetime


class CheckRuleSummary(DomainModel):
    rule_family: str
    status: str
    issue_count: int = 0


class SceneDraftCheckReport(DomainModel):
    report_id: str
    project_id: str
    volume_id: str
    chapter_id: str
    scene_id: str
    draft_id: str
    trigger: str
    checker_version: str = "deterministic_v1"
    created_at: datetime
    source_versions: CheckSourceVersions
    overall_status: str
    blocker_count: int = 0
    warning_count: int = 0
    issues: list[ConsistencyIssue] = Field(default_factory=list)
    rule_summaries: list[CheckRuleSummary] = Field(default_factory=list)


class ChapterCheckSourceVersions(DomainModel):
    volume_version: int = 0
    chapter_version: int = 0
    scene_versions: dict[str, int] = Field(default_factory=dict)
    accepted_draft_ids: dict[str, str] = Field(default_factory=dict)
    assembled_version: int = 0


class ChapterCheckReport(DomainModel):
    report_id: str
    project_id: str
    volume_id: str
    chapter_id: str
    trigger: str
    checker_version: str = "deterministic_v1"
    created_at: datetime
    source_versions: ChapterCheckSourceVersions
    overall_status: str
    blocker_count: int = 0
    warning_count: int = 0
    issues: list[ConsistencyIssue] = Field(default_factory=list)
    rule_summaries: list[CheckRuleSummary] = Field(default_factory=list)


class VolumeCheckSourceVersions(DomainModel):
    volume_version: int = 0
    planned_chapter_versions: dict[str, int] = Field(default_factory=dict)
    finalized_chapter_versions: dict[str, int] = Field(default_factory=dict)
    assembled_version: int = 0


class VolumeCheckReport(DomainModel):
    report_id: str
    project_id: str
    volume_id: str
    trigger: str
    checker_version: str = "deterministic_v1"
    created_at: datetime
    source_versions: VolumeCheckSourceVersions
    overall_status: str
    blocker_count: int = 0
    warning_count: int = 0
    issues: list[ConsistencyIssue] = Field(default_factory=list)
    rule_summaries: list[CheckRuleSummary] = Field(default_factory=list)
