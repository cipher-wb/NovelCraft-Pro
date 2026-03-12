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
