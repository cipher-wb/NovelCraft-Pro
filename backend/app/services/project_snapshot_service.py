from __future__ import annotations

import json
import shutil
import uuid
from pathlib import Path

from backend.app.core.paths import AppPaths
from backend.app.domain.models.common import utc_now
from backend.app.domain.models.writing import SnapshotListItem, SnapshotResult
from backend.app.repositories.file_repository import FileRepository
from backend.app.repositories.sqlite_repository import SQLiteRepository
from backend.app.services.export_service import ExportService


class ProjectSnapshotService:
    def __init__(
        self,
        paths: AppPaths,
        file_repository: FileRepository,
        sqlite_repository: SQLiteRepository,
        export_service: ExportService,
    ) -> None:
        self.paths = paths
        self.file_repository = file_repository
        self.sqlite_repository = sqlite_repository
        self.export_service = export_service

    def create_archive_snapshot(self, project_id: str, *, label: str = "", format: str = "json_package") -> SnapshotResult:
        return self._create_snapshot(project_id, snapshot_type="archive", label=label, format=format)

    def create_backup(self, project_id: str, *, format: str = "json_package") -> SnapshotResult:
        return self._create_snapshot(project_id, snapshot_type="backup", label="", format=format)

    def list_snapshots(self, project_id: str) -> list[SnapshotListItem]:
        project = self._require_project(project_id)
        slug = project["slug"]
        items: list[SnapshotListItem] = []
        for root in [self.paths.archives_dir(slug), self.paths.backups_dir(slug)]:
            if not root.exists():
                continue
            for snapshot_json in sorted(root.glob("*/snapshot.json")):
                payload = json.loads(snapshot_json.read_text(encoding="utf-8"))
                result = SnapshotResult.model_validate(payload)
                items.append(
                    SnapshotListItem(
                        snapshot_id=result.snapshot_id,
                        snapshot_type=result.snapshot_type,
                        created_at=result.created_at,
                        label=result.label,
                        project_id=result.project_id,
                        project_slug=result.project_slug,
                        relative_dir=result.relative_dir,
                    )
                )
        return sorted(items, key=lambda item: item.created_at, reverse=True)

    def _create_snapshot(self, project_id: str, *, snapshot_type: str, label: str, format: str) -> SnapshotResult:
        project = self._require_project(project_id)
        slug = project["slug"]
        package = self.export_service.export(project_id, scope="project", target_id=None, format=format)
        package_root = self.paths.project_root(slug) / package.relative_dir
        snapshot_id = self._new_snapshot_id()
        snapshot_dir = (
            self.paths.archive_snapshot_dir(slug, snapshot_id)
            if snapshot_type == "archive"
            else self.paths.backup_snapshot_dir(slug, snapshot_id)
        )
        self.file_repository.ensure_dir(snapshot_dir.parent)
        shutil.copytree(package_root, snapshot_dir)
        result = SnapshotResult(
            snapshot_id=snapshot_id,
            snapshot_type=snapshot_type,
            created_at=utc_now(),
            label=label,
            project_id=project_id,
            project_slug=slug,
            package_id=package.package_id or package.export_id,
            package_version=package.package_version or ExportService.PROJECT_PACKAGE_VERSION,
            format=package.format,
            relative_dir=self.paths.relative_to_project(slug, snapshot_dir),
            relative_package_path=self.paths.relative_to_project(slug, snapshot_dir),
            warnings=package.warnings,
        )
        self.file_repository.write_json(snapshot_dir / "snapshot.json", result.model_dump(mode="json"))
        return result

    def _new_snapshot_id(self) -> str:
        return f"{utc_now().strftime('%Y%m%dT%H%M%SZ')}-{uuid.uuid4().hex[:8]}"

    def _require_project(self, project_id: str) -> dict[str, object]:
        project = self.sqlite_repository.get_project_record(project_id)
        if project is None:
            raise KeyError(project_id)
        return project
