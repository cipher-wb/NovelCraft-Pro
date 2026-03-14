from __future__ import annotations

import hashlib
import json
import re
import uuid
from pathlib import Path, PurePosixPath
from typing import Any

from backend.app.core.paths import AppPaths
from backend.app.domain.models.common import utc_now
from backend.app.domain.models.planning import ChapterPlan, MasterOutlineDocument, ScenePlan, VolumePlan
from backend.app.domain.models.project import CharacterDocument, PowerSystemDocument, ProjectManifest, StoryBible, WorldDocument
from backend.app.domain.models.style import VoiceProfileDocument
from backend.app.domain.models.writing import ExportPackageManifest, ImportReport, ProjectHealthReport, ProjectPackageInventory
from backend.app.repositories.file_repository import FileRepository
from backend.app.repositories.sqlite_repository import SQLiteRepository
from backend.app.services.exceptions import ConflictError
from backend.app.services.project_health_service import ProjectHealthService


class ImportService:
    SUPPORTED_PACKAGE_VERSION = "project_package_v1"
    REQUIRED_CANONICAL_FILES = (
        "canonical/project.json",
        "canonical/bible/story_bible.json",
        "canonical/bible/characters.json",
        "canonical/bible/world.json",
        "canonical/bible/power_system.json",
        "canonical/bible/voice_profile.json",
        "canonical/plans/master_outline.json",
    )

    def __init__(
        self,
        paths: AppPaths,
        file_repository: FileRepository,
        sqlite_repository: SQLiteRepository,
        bible_service,
        planner_service,
        health_service: ProjectHealthService,
    ) -> None:
        self.paths = paths
        self.file_repository = file_repository
        self.sqlite_repository = sqlite_repository
        self.bible_service = bible_service
        self.planner_service = planner_service
        self.health_service = health_service

    def import_package(
        self,
        package_path: str,
        *,
        new_project_id: str | None = None,
        new_project_slug: str | None = None,
        mode: str = "create_new",
    ) -> ImportReport:
        if mode != "create_new":
            raise ValueError("Only create_new import mode is supported.")
        root = self._resolve_package_path(package_path)
        if not root.exists():
            raise KeyError(package_path)

        manifest = ExportPackageManifest.model_validate(self.file_repository.read_json(root / "manifest.json"))
        inventory = ProjectPackageInventory.model_validate(self.file_repository.read_json(root / "inventory.json"))
        self._validate_manifest_and_inventory(root, manifest, inventory)
        source_manifest = ProjectManifest.model_validate(self.file_repository.read_json(root / "canonical" / "project.json"))
        self._validate_canonical(root, inventory)

        imported_project_id = new_project_id or self._new_project_id()
        imported_slug = self._resolve_slug(source_manifest.slug, new_project_slug)
        self._assert_project_available(imported_project_id, imported_slug, new_project_id is not None, new_project_slug is not None)

        now = utc_now()
        project_root = self.paths.project_root(imported_slug)
        self.file_repository.ensure_dir(project_root)
        restored_count = 0
        for item in inventory.items:
            source_path = root / item.relative_path
            destination = self._map_package_path_to_project_root(project_root, item.relative_path)
            self.file_repository.ensure_dir(destination.parent)
            if source_path.suffix == ".json":
                payload = json.loads(source_path.read_text(encoding="utf-8"))
                rewritten = self._rewrite_project_ids(payload, imported_project_id)
                if item.relative_path == "canonical/project.json":
                    rewritten["project_id"] = imported_project_id
                    rewritten["slug"] = imported_slug
                    rewritten["updated_at"] = now.isoformat()
                self.file_repository.write_json(destination, rewritten)
            else:
                destination.write_bytes(source_path.read_bytes())
            restored_count += 1

        imported_manifest = ProjectManifest.model_validate(self.file_repository.read_json(project_root / "project.json"))
        self.sqlite_repository.create_project_record(
            {
                "project_id": imported_project_id,
                "slug": imported_slug,
                "title": imported_manifest.title,
                "genre": imported_manifest.genre,
                "status": imported_manifest.status,
                "target_chapters": imported_manifest.target_chapters,
                "target_words": imported_manifest.target_words,
                "root_path": str(project_root),
                "manifest_path": str(project_root / "project.json"),
                "created_at": imported_manifest.created_at.isoformat(),
                "updated_at": now.isoformat(),
            }
        )
        post_import_health = self.health_service.build_report(imported_project_id)
        return ImportReport(
            package_id=inventory.package_id,
            package_version=inventory.package_version,
            project_id=imported_project_id,
            project_slug=imported_slug,
            mode=mode,
            imported_at=now,
            restored_file_count=restored_count,
            warnings=[],
            post_import_health=ProjectHealthReport.model_validate(post_import_health),
        )

    def _validate_manifest_and_inventory(
        self,
        root: Path,
        manifest: ExportPackageManifest,
        inventory: ProjectPackageInventory,
    ) -> None:
        if manifest.scope != "project":
            raise ConflictError("Only project packages can be imported.")
        if manifest.package_version != self.SUPPORTED_PACKAGE_VERSION or inventory.package_version != self.SUPPORTED_PACKAGE_VERSION:
            raise ValueError("Unsupported package_version.")
        if manifest.package_id != inventory.package_id:
            raise ValueError("Manifest and inventory package_id mismatch.")

        inventory_paths = {item.relative_path for item in inventory.items}
        for required in self.REQUIRED_CANONICAL_FILES:
            if required not in inventory_paths:
                raise ValueError(f"Missing required canonical file: {required}")

        for item in inventory.items:
            self._validate_relative_path(item.relative_path)
            path = root / item.relative_path
            if not path.exists():
                raise ValueError(f"Inventory-declared file missing: {item.relative_path}")
            if self._sha256(path) != item.sha256:
                raise ValueError(f"Hash mismatch for {item.relative_path}")
            if path.stat().st_size != item.size_bytes:
                raise ValueError(f"Size mismatch for {item.relative_path}")

    def _validate_canonical(self, root: Path, inventory: ProjectPackageInventory) -> None:
        for item in inventory.items:
            path = item.relative_path
            full_path = root / path
            if path == "canonical/project.json":
                ProjectManifest.model_validate(self.file_repository.read_json(full_path))
            elif path == "canonical/bible/story_bible.json":
                StoryBible.model_validate(self.file_repository.read_json(full_path))
            elif path == "canonical/bible/characters.json":
                CharacterDocument.model_validate(self.file_repository.read_json(full_path))
            elif path == "canonical/bible/world.json":
                WorldDocument.model_validate(self.file_repository.read_json(full_path))
            elif path == "canonical/bible/power_system.json":
                PowerSystemDocument.model_validate(self.file_repository.read_json(full_path))
            elif path == "canonical/bible/voice_profile.json":
                VoiceProfileDocument.model_validate(self.file_repository.read_json(full_path))
            elif path == "canonical/plans/master_outline.json":
                MasterOutlineDocument.model_validate(self.file_repository.read_json(full_path))
            elif path.startswith("canonical/plans/volumes/"):
                VolumePlan.model_validate(self.file_repository.read_json(full_path))
            elif path.startswith("canonical/plans/chapters/"):
                ChapterPlan.model_validate(self.file_repository.read_json(full_path))
            elif path.startswith("canonical/plans/scenes/"):
                ScenePlan.model_validate(self.file_repository.read_json(full_path))

    def _map_package_path_to_project_root(self, project_root: Path, relative_path: str) -> Path:
        path = PurePosixPath(relative_path)
        head = path.parts[0]
        remainder = path.parts[1:]
        if head == "canonical":
            if remainder and remainder[0] == "project.json":
                return project_root / "project.json"
            return project_root.joinpath(*remainder)
        if head == "derived":
            return project_root.joinpath(*remainder)
        if head == "memory":
            return project_root.joinpath("memory", *remainder)
        if head == "checks":
            return project_root.joinpath("drafts", *remainder)
        if head == "markdown":
            return project_root.joinpath("markdown", *remainder)
        raise ValueError(f"Unsupported package path: {relative_path}")

    def _rewrite_project_ids(self, payload: Any, new_project_id: str) -> Any:
        if isinstance(payload, dict):
            return {
                key: (new_project_id if key == "project_id" else self._rewrite_project_ids(value, new_project_id))
                for key, value in payload.items()
            }
        if isinstance(payload, list):
            return [self._rewrite_project_ids(item, new_project_id) for item in payload]
        return payload

    def _assert_project_available(
        self,
        project_id: str,
        slug: str,
        project_id_explicit: bool,
        slug_explicit: bool,
    ) -> None:
        if self.sqlite_repository.get_project_record(project_id) is not None:
            raise ConflictError("Target project_id already exists.")
        if self.sqlite_repository.get_project_record_by_slug(slug) is not None:
            raise ConflictError("Target project slug already exists.")
        if project_id_explicit and self.sqlite_repository.get_project_record(project_id) is not None:
            raise ConflictError("Target project_id already exists.")
        if slug_explicit and self.sqlite_repository.get_project_record_by_slug(slug) is not None:
            raise ConflictError("Target project slug already exists.")

    def _resolve_slug(self, source_slug: str, requested_slug: str | None) -> str:
        if requested_slug:
            return requested_slug
        base = f"{source_slug}-imported"
        slug = base
        index = 2
        while self.sqlite_repository.get_project_record_by_slug(slug) is not None:
            slug = f"{base}-{index}"
            index += 1
        return slug

    def _validate_relative_path(self, relative_path: str) -> None:
        path = PurePosixPath(relative_path)
        if path.is_absolute() or path.drive:
            raise ValueError("Inventory contains absolute path.")
        if any(part in {"..", ""} for part in path.parts):
            raise ValueError("Inventory contains invalid relative path.")
        if re.match(r"^[A-Za-z]:", relative_path):
            raise ValueError("Inventory contains machine-specific path.")

    def _new_project_id(self) -> str:
        return f"proj_{uuid.uuid4().hex[:12]}"

    def _sha256(self, path: Path) -> str:
        digest = hashlib.sha256()
        digest.update(path.read_bytes())
        return digest.hexdigest()

    def _resolve_package_path(self, package_path: str) -> Path:
        root = Path(package_path)
        if root.exists():
            return root
        if root.is_absolute():
            return root
        for record in self.sqlite_repository.list_project_records():
            candidate = self.paths.project_root(record["slug"]) / root
            if candidate.exists():
                return candidate
        return root
