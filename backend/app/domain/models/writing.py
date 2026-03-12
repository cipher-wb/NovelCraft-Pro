from __future__ import annotations

from datetime import datetime
from pydantic import Field

from backend.app.domain.models.common import DomainModel


class SceneDraft(DomainModel):
    draft_id: str
    project_id: str
    chapter_id: str
    scene_id: str
    operation: str
    status: str
    content_md: str
    summary: str = ""
    context_bundle_id: str | None = None
    model_name: str = ""
    tokens_in: int = 0
    tokens_out: int = 0
    created_at: datetime
    accepted_at: datetime | None = None
    supersedes_draft_id: str | None = None


class CharacterStateSnapshot(DomainModel):
    snapshot_id: str
    project_id: str
    character_id: str
    chapter_id: str
    scene_id: str | None = None
    realm_level: str = ""
    health_status: str = ""
    location: str = ""
    inventory: list[str] = Field(default_factory=list)
    alliances: list[str] = Field(default_factory=list)
    hostilities: list[str] = Field(default_factory=list)
    goals: list[str] = Field(default_factory=list)
    emotion: str = ""
    knowledge: list[str] = Field(default_factory=list)
    created_at: datetime


class TimelineEvent(DomainModel):
    event_id: str
    project_id: str
    chapter_id: str
    scene_id: str | None = None
    time_order: int
    event_time: str = ""
    title: str
    description: str = ""
    participants: list[str] = Field(default_factory=list)
    location: str = ""
    event_type: str = ""
    causes: list[str] = Field(default_factory=list)
    effects: list[str] = Field(default_factory=list)
    source_version_id: str | None = None


class DraftVersion(DomainModel):
    version_id: str
    project_id: str
    scope: str
    scope_id: str
    base_version_id: str | None = None
    source_draft_id: str | None = None
    content_md: str
    change_note: str = ""
    created_by: str
    created_at: datetime
    checksum: str = ""
    snapshot_path: str
    is_active: bool = True
