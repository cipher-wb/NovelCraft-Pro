from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class ExportProjectRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    scope: str
    target_id: str | None = None
    format: str = "markdown_package"


class RebuildProjectRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    targets: list[str] = Field(default_factory=list)
