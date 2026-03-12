from __future__ import annotations

import re
import uuid
from typing import Any

from backend.app.core.paths import AppPaths
from backend.app.domain.models.common import ProjectStatus, utc_now
from backend.app.domain.models.project import ProjectManifest
from backend.app.repositories.file_repository import FileRepository
from backend.app.repositories.sqlite_repository import SQLiteRepository
from backend.app.repositories.vector_repository import VectorRepository
from backend.app.schemas.project import CreateProjectRequest, ProjectPathsResponse
from backend.app.services.bootstrap_service import BootstrapService


class ProjectService:
    def __init__(
        self,
        paths: AppPaths,
        file_repository: FileRepository,
        sqlite_repository: SQLiteRepository,
        vector_repository: VectorRepository,
        bootstrap_service: BootstrapService,
    ) -> None:
        self.paths = paths
        self.file_repository = file_repository
        self.sqlite_repository = sqlite_repository
        self.vector_repository = vector_repository
        self.bootstrap_service = bootstrap_service

    def create_project(self, request: CreateProjectRequest) -> tuple[ProjectManifest, ProjectPathsResponse]:
        now = utc_now()
        project_id = f"proj_{uuid.uuid4().hex[:12]}"
        slug = self._build_unique_slug(request.title)
        manifest = ProjectManifest(
            project_id=project_id,
            slug=slug,
            title=request.title,
            genre=request.genre,
            status=ProjectStatus.bootstrapped.value,
            target_chapters=request.target_chapters,
            target_words=request.target_words,
            created_at=now,
            updated_at=now,
        )
        manifest_payload = manifest.model_dump(mode="json")
        project_paths = self.bootstrap_service.initialize_project_structure(slug, manifest_payload)
        self.vector_repository.ensure_project_namespace(project_id)
        self.sqlite_repository.create_project_record(
            {
                "project_id": manifest.project_id,
                "slug": manifest.slug,
                "title": manifest.title,
                "genre": manifest.genre,
                "status": manifest.status,
                "target_chapters": manifest.target_chapters,
                "target_words": manifest.target_words,
                "root_path": str(project_paths["root"]),
                "manifest_path": str(self.paths.project_manifest_path(slug)),
                "created_at": manifest.created_at.isoformat(),
                "updated_at": manifest.updated_at.isoformat(),
            }
        )
        return manifest, self._to_paths_response(slug)

    def list_projects(self) -> list[ProjectManifest]:
        return [self._record_to_manifest(record) for record in self.sqlite_repository.list_project_records()]

    def get_project(self, project_id: str) -> ProjectManifest:
        record = self.sqlite_repository.get_project_record(project_id)
        if record is None:
            raise KeyError(project_id)
        return self._record_to_manifest(record)

    def get_project_paths(self, project_id: str) -> ProjectPathsResponse:
        manifest = self.get_project(project_id)
        return self._to_paths_response(manifest.slug)

    def _record_to_manifest(self, record: dict[str, Any]) -> ProjectManifest:
        return ProjectManifest.model_validate(record)

    def _to_paths_response(self, slug: str) -> ProjectPathsResponse:
        return ProjectPathsResponse(
            root=str(self.paths.project_root(slug)),
            consultant_dir=str(self.paths.consultant_dir(slug)),
            bible_dir=str(self.paths.bible_dir(slug)),
            plans_dir=str(self.paths.plans_dir(slug)),
            drafts_dir=str(self.paths.drafts_dir(slug)),
            memory_dir=str(self.paths.memory_dir(slug)),
            meta_dir=str(self.paths.meta_dir(slug)),
        )

    def _build_unique_slug(self, title: str) -> str:
        base = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")
        if not base:
            base = f"project-{uuid.uuid4().hex[:8]}"
        slug = base
        suffix = 1
        while self.sqlite_repository.get_project_record_by_slug(slug) is not None:
            suffix += 1
            slug = f"{base}-{suffix}"
        return slug
