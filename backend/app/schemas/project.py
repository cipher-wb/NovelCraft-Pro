from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from backend.app.domain.models.project import ProjectManifest


class CreateProjectRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=1)
    genre: str = Field(min_length=1)
    target_chapters: int = Field(gt=0)
    target_words: int = Field(gt=0)


class CreateProjectResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    project_id: str
    slug: str
    manifest: ProjectManifest


class ProjectListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[ProjectManifest]


class ProjectPathsResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    root: str
    consultant_dir: str
    bible_dir: str
    plans_dir: str
    drafts_dir: str
    memory_dir: str
    meta_dir: str


class ProjectDetailResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    manifest: ProjectManifest
    paths: ProjectPathsResponse
