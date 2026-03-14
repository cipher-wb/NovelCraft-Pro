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


class ImportProjectPackageRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    package_path: str
    new_project_id: str | None = None
    new_project_slug: str | None = None
    mode: str = "create_new"


class ArchiveSnapshotRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    label: str = ""
    format: str = "json_package"


class BackupProjectRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    format: str = "json_package"
