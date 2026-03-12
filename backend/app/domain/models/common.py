from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum

from pydantic import BaseModel, ConfigDict


class DomainModel(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)


class ProjectStatus(str, Enum):
    bootstrapped = "bootstrapped"
    active = "active"
    archived = "archived"


class SessionStatus(str, Enum):
    in_progress = "in_progress"
    completed = "completed"


class DraftStatus(str, Enum):
    draft = "draft"
    accepted = "accepted"
    rejected = "rejected"
    superseded = "superseded"


class IssueSeverity(str, Enum):
    low = "low"
    medium = "medium"
    high = "high"
    blocker = "blocker"


class IssueStatus(str, Enum):
    open = "open"
    resolved = "resolved"
    ignored = "ignored"


class ForeshadowStatus(str, Enum):
    open = "open"
    paid_off = "paid_off"
    abandoned = "abandoned"


class PayoffStatus(str, Enum):
    planned = "planned"
    delivered = "delivered"
    missed = "missed"


def utc_now() -> datetime:
    return datetime.now(timezone.utc)
