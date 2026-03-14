from __future__ import annotations

import hashlib
import shutil
import uuid
from pathlib import Path
from typing import Any

from backend.app.core.paths import AppPaths
from backend.app.domain.models.common import utc_now
from backend.app.domain.models.writing import (
    BookAssembledDocument,
    ExportPackageManifest,
    ExportResult,
    ProjectPackageInventory,
    ProjectPackageInventoryItem,
    SceneDraft,
    VolumeAssembledDocument,
    ChapterAssembledDocument,
)
from backend.app.repositories.file_repository import FileRepository
from backend.app.repositories.sqlite_repository import SQLiteRepository
from backend.app.services.exceptions import ConflictError
from backend.app.services.planner_service import PlannerService


class ExportService:
    PROJECT_PACKAGE_VERSION = "project_package_v1"
    SUPPORTED_SCOPES = {"scene", "chapter", "volume", "book", "project"}
    SUPPORTED_FORMATS = {"markdown_package", "json_package"}

    def __init__(
        self,
        paths: AppPaths,
        file_repository: FileRepository,
        sqlite_repository: SQLiteRepository,
        planner_service: PlannerService,
    ) -> None:
        self.paths = paths
        self.file_repository = file_repository
        self.sqlite_repository = sqlite_repository
        self.planner_service = planner_service

    def export(self, project_id: str, scope: str, target_id: str | None, format: str) -> ExportResult:
        if scope not in self.SUPPORTED_SCOPES:
            raise ValueError("Unsupported export scope.")
        if format not in self.SUPPORTED_FORMATS:
            raise ValueError("Unsupported export format.")

        project = self._require_project(project_id)
        slug = project["slug"]
        resolved_target_id = "book" if scope == "book" and not target_id else (target_id or "")
        if scope == "project":
            resolved_target_id = "project"
        if not resolved_target_id:
            raise ValueError("target_id is required for this export scope.")

        export_id = self._new_export_id()
        created_at = utc_now()
        warnings: list[str] = []

        if scope == "project":
            return self._export_project_package(
                slug=slug,
                project_id=project_id,
                package_id=export_id,
                format=format,
                created_at=created_at,
                warnings=warnings,
            )

        if scope == "scene":
            content_md, source_status, artifacts = self._build_scene_export(slug, project_id, resolved_target_id, warnings)
            export_dir = self.paths.scene_export_dir(slug, resolved_target_id, export_id)
        elif scope == "chapter":
            content_md, source_status, artifacts = self._build_chapter_export(slug, project_id, resolved_target_id, warnings)
            export_dir = self.paths.chapter_export_dir(slug, resolved_target_id, export_id)
        elif scope == "volume":
            content_md, source_status, artifacts = self._build_volume_export(slug, project_id, resolved_target_id, warnings)
            export_dir = self.paths.volume_export_dir(slug, resolved_target_id, export_id)
        else:
            content_md, source_status, artifacts = self._build_book_export(slug, project_id, warnings)
            export_dir = self.paths.book_export_dir(slug, export_id)
            resolved_target_id = "book"

        included_files: list[str] = []
        self.file_repository.ensure_dir(export_dir)
        artifacts_dir = export_dir / "artifacts"
        self.file_repository.ensure_dir(artifacts_dir)

        if format == "markdown_package":
            self.file_repository.write_text(export_dir / "content.md", content_md)
            included_files.append("content.md")
        for filename, payload in artifacts.items():
            self.file_repository.write_json(artifacts_dir / filename, self._json_payload(payload))
            included_files.append(f"artifacts/{filename}")

        manifest = ExportPackageManifest(
            export_id=export_id,
            scope=scope,
            target_id=resolved_target_id,
            format=format,
            created_at=created_at,
            source_status=source_status,
            included_files=["manifest.json", *included_files],
            warnings=warnings,
        )
        self.file_repository.write_json(export_dir / "manifest.json", manifest.model_dump(mode="json"))

        relative_dir = self.paths.relative_to_project(slug, export_dir)
        return ExportResult(
            **manifest.model_dump(mode="python"),
            relative_dir=relative_dir,
            relative_package_path=relative_dir,
        )

    def _export_project_package(
        self,
        *,
        slug: str,
        project_id: str,
        package_id: str,
        format: str,
        created_at,
        warnings: list[str],
    ) -> ExportResult:
        package_dir = self.paths.project_export_dir(slug, package_id)
        self.file_repository.ensure_dir(package_dir)

        package_files: list[tuple[str, Path]] = []
        package_files.extend(self._collect_project_package_files(slug))

        inventory_items: list[ProjectPackageInventoryItem] = []
        for relative_path, source_path in sorted(package_files, key=lambda item: item[0]):
            destination = package_dir / relative_path
            self.file_repository.ensure_dir(destination.parent)
            shutil.copyfile(source_path, destination)
            inventory_items.append(
                ProjectPackageInventoryItem(
                    relative_path=relative_path,
                    file_kind=self._classify_project_package_file(relative_path),
                    sha256=self._sha256(destination),
                    size_bytes=destination.stat().st_size,
                )
            )

        if format == "markdown_package":
            for relative_path in self._write_project_markdown_files(slug, project_id, package_dir, warnings):
                destination = package_dir / relative_path
                inventory_items.append(
                    ProjectPackageInventoryItem(
                        relative_path=relative_path,
                        file_kind="markdown",
                        sha256=self._sha256(destination),
                        size_bytes=destination.stat().st_size,
                    )
                )

        inventory = ProjectPackageInventory(
            package_id=package_id,
            package_version=self.PROJECT_PACKAGE_VERSION,
            created_at=created_at,
            items=sorted(inventory_items, key=lambda item: item.relative_path),
        )
        self.file_repository.write_json(package_dir / "inventory.json", inventory.model_dump(mode="json"))

        included_files = ["manifest.json", "inventory.json", "canonical/", "derived/", "memory/", "checks/"]
        if format == "markdown_package":
            included_files.append("markdown/")
        manifest = ExportPackageManifest(
            export_id=package_id,
            package_id=package_id,
            scope="project",
            target_id="project",
            format=format,
            created_at=created_at,
            package_version=self.PROJECT_PACKAGE_VERSION,
            source_status="project_snapshot",
            included_files=included_files,
            warnings=warnings,
        )
        self.file_repository.write_json(package_dir / "manifest.json", manifest.model_dump(mode="json"))
        relative_dir = self.paths.relative_to_project(slug, package_dir)
        return ExportResult(
            **manifest.model_dump(mode="python"),
            relative_dir=relative_dir,
            relative_package_path=relative_dir,
        )

    def _build_scene_export(
        self,
        slug: str,
        project_id: str,
        scene_id: str,
        warnings: list[str],
    ) -> tuple[str, str, dict[str, Any]]:
        self.planner_service.get_scene(project_id, scene_id)
        accepted_drafts = self._accepted_drafts_for_scene(slug, scene_id)
        if len(accepted_drafts) != 1:
            raise ConflictError("Scene export requires exactly one active accepted draft.")
        draft = accepted_drafts[0]
        artifacts: dict[str, Any] = {"accepted_draft.json": draft}
        context_bundle = self._optional_json(slug, draft.context_bundle_path)
        if context_bundle is None:
            warnings.append("context_bundle_missing")
        else:
            artifacts["context_bundle.json"] = context_bundle
        latest_checks = self._optional_json(slug, draft.latest_check_report_path)
        if latest_checks is None:
            warnings.append("latest_check_report_missing")
        else:
            artifacts["latest_checks.json"] = latest_checks
        return draft.content_md, "accepted", artifacts

    def _build_chapter_export(
        self,
        slug: str,
        project_id: str,
        chapter_id: str,
        warnings: list[str],
    ) -> tuple[str, str, dict[str, Any]]:
        self.planner_service.get_chapter(project_id, chapter_id)
        path = self.paths.chapter_assembled_path(slug, chapter_id)
        if not self.file_repository.exists(path):
            raise ConflictError("Chapter export requires an assembled chapter artifact.")
        artifact = ChapterAssembledDocument.model_validate(self.file_repository.read_json(path))
        artifacts: dict[str, Any] = {"assembled.json": artifact}
        latest_checks = self._optional_json(slug, artifact.latest_check_report_path)
        if latest_checks is None:
            warnings.append("latest_check_report_missing")
        else:
            artifacts["latest_checks.json"] = latest_checks
        return artifact.content_md, artifact.status, artifacts

    def _build_volume_export(
        self,
        slug: str,
        project_id: str,
        volume_id: str,
        warnings: list[str],
    ) -> tuple[str, str, dict[str, Any]]:
        self.planner_service.get_volume(project_id, volume_id)
        path = self.paths.volume_assembled_path(slug, volume_id)
        if not self.file_repository.exists(path):
            raise ConflictError("Volume export requires an assembled volume artifact.")
        artifact = VolumeAssembledDocument.model_validate(self.file_repository.read_json(path))
        artifacts: dict[str, Any] = {"assembled.json": artifact}
        latest_checks = self._optional_json(slug, artifact.latest_check_report_path)
        if latest_checks is None:
            warnings.append("latest_check_report_missing")
        else:
            artifacts["latest_checks.json"] = latest_checks
        return artifact.content_md, artifact.status, artifacts

    def _build_book_export(
        self,
        slug: str,
        project_id: str,
        warnings: list[str],
    ) -> tuple[str, str, dict[str, Any]]:
        self._require_project(project_id)
        path = self.paths.book_assembled_path(slug)
        if not self.file_repository.exists(path):
            raise ConflictError("Book export requires an assembled book artifact.")
        artifact = BookAssembledDocument.model_validate(self.file_repository.read_json(path))
        artifacts: dict[str, Any] = {"assembled.json": artifact}
        latest_checks = self._optional_json(slug, artifact.latest_check_report_path)
        if latest_checks is None:
            warnings.append("latest_check_report_missing")
        else:
            artifacts["latest_checks.json"] = latest_checks
        continuity_checks = self._optional_json(slug, artifact.latest_continuity_check_report_path)
        if continuity_checks is not None:
            artifacts["latest_continuity_checks.json"] = continuity_checks
        return artifact.content_md, artifact.status, artifacts

    def _accepted_drafts_for_scene(self, slug: str, scene_id: str) -> list[SceneDraft]:
        scene_dir = self.paths.scene_drafts_dir(slug, scene_id)
        if not scene_dir.exists():
            return []
        accepted: list[SceneDraft] = []
        for draft_path in sorted(scene_dir.glob("draft-*.json")):
            draft = SceneDraft.model_validate(self.file_repository.read_json(draft_path))
            if draft.status == "accepted":
                accepted.append(draft)
        return accepted

    def _optional_json(self, slug: str, relative_path: str | None) -> Any | None:
        if not relative_path:
            return None
        path = self.paths.project_root(slug) / relative_path
        if not self.file_repository.exists(path):
            return None
        return self.file_repository.read_json(path)

    def _json_payload(self, payload: Any) -> Any:
        if hasattr(payload, "model_dump"):
            return payload.model_dump(mode="json")
        return payload

    def _new_export_id(self) -> str:
        return f"{utc_now().strftime('%Y%m%dT%H%M%SZ')}-{uuid.uuid4().hex[:8]}"

    def _require_project(self, project_id: str) -> dict[str, Any]:
        project = self.sqlite_repository.get_project_record(project_id)
        if project is None:
            raise KeyError(project_id)
        return project

    def _collect_project_package_files(self, slug: str) -> list[tuple[str, Path]]:
        files: list[tuple[str, Path]] = []
        canonical_files = [
            (self.paths.project_manifest_path(slug), "canonical/project.json"),
            (self.paths.story_bible_path(slug), "canonical/bible/story_bible.json"),
            (self.paths.characters_path(slug), "canonical/bible/characters.json"),
            (self.paths.world_path(slug), "canonical/bible/world.json"),
            (self.paths.power_system_path(slug), "canonical/bible/power_system.json"),
            (self.paths.voice_profile_path(slug), "canonical/bible/voice_profile.json"),
            (self.paths.master_outline_path(slug), "canonical/plans/master_outline.json"),
        ]
        for source_path, relative_path in canonical_files:
            if self.file_repository.exists(source_path):
                files.append((relative_path, source_path))

        for root, package_root in [
            (self.paths.volumes_dir(slug), "canonical/plans/volumes"),
            (self.paths.chapters_dir(slug), "canonical/plans/chapters"),
            (self.paths.scenes_dir(slug), "canonical/plans/scenes"),
            (self.paths.scene_drafts_root(slug), "derived/drafts/scenes"),
            (self.paths.chapter_drafts_root(slug), "derived/drafts/chapters"),
            (self.paths.volume_drafts_root(slug), "derived/drafts/volumes"),
            (self.paths.book_drafts_root(slug), "derived/drafts/book"),
            (self.paths.memory_dir(slug), "memory"),
        ]:
            files.extend(self._walk_tree(root, package_root))

        checks_roots = [
            self.paths.scene_drafts_root(slug),
            self.paths.chapter_drafts_root(slug),
            self.paths.volume_drafts_root(slug),
            self.paths.book_drafts_root(slug),
        ]
        for checks_root in checks_roots:
            if not checks_root.exists():
                continue
            for file_path in sorted(checks_root.rglob("*.json")):
                if "checks" not in file_path.parts and "continuity_checks" not in file_path.parts:
                    continue
                relative_under_root = file_path.relative_to(self.paths.drafts_dir(slug)).as_posix()
                files.append((f"checks/{relative_under_root}", file_path))

        deduped: dict[str, Path] = {}
        for relative_path, source_path in files:
            if relative_path.startswith("derived/") and ("/checks/" in relative_path or "/continuity_checks/" in relative_path):
                continue
            deduped[relative_path] = source_path
        return sorted(deduped.items(), key=lambda item: item[0])

    def _walk_tree(self, root: Path, package_root: str) -> list[tuple[str, Path]]:
        if not root.exists():
            return []
        items: list[tuple[str, Path]] = []
        for file_path in sorted(root.rglob("*.json")):
            relative = file_path.relative_to(root).as_posix()
            items.append((f"{package_root}/{relative}", file_path))
        return items

    def _write_project_markdown_files(
        self,
        slug: str,
        project_id: str,
        package_dir: Path,
        warnings: list[str],
    ) -> list[str]:
        items: list[str] = []

        book_path = self.paths.book_assembled_path(slug)
        if self.file_repository.exists(book_path):
            book = BookAssembledDocument.model_validate(self.file_repository.read_json(book_path))
            self.file_repository.write_text(package_dir / "markdown" / "book.md", book.content_md)
            items.append("markdown/book.md")

        for volume in self.planner_service.list_volumes(project_id):
            volume_path = self.paths.volume_assembled_path(slug, volume.volume_id)
            if self.file_repository.exists(volume_path):
                artifact = VolumeAssembledDocument.model_validate(self.file_repository.read_json(volume_path))
                file_path = package_dir / "markdown" / "volumes" / f"{volume.volume_no:03d}-{volume.volume_id}.md"
                self.file_repository.write_text(file_path, artifact.content_md)
                items.append(f"markdown/volumes/{volume.volume_no:03d}-{volume.volume_id}.md")
            for chapter in self.planner_service.list_chapters(project_id, volume.volume_id):
                chapter_path = self.paths.chapter_assembled_path(slug, chapter.chapter_id)
                if self.file_repository.exists(chapter_path):
                    artifact = ChapterAssembledDocument.model_validate(self.file_repository.read_json(chapter_path))
                    file_path = package_dir / "markdown" / "chapters" / f"{chapter.chapter_no:04d}-{chapter.chapter_id}.md"
                    self.file_repository.write_text(file_path, artifact.content_md)
                    items.append(f"markdown/chapters/{chapter.chapter_no:04d}-{chapter.chapter_id}.md")
                for scene in self.planner_service.list_scenes(project_id, chapter.chapter_id):
                    accepted = self._accepted_drafts_for_scene(slug, scene.scene_id)
                    if len(accepted) != 1:
                        warnings.append(f"scene_markdown_missing_unique_accepted:{scene.scene_id}")
                        continue
                    draft = accepted[0]
                    file_path = package_dir / "markdown" / "scenes" / f"{chapter.chapter_no:04d}-{scene.scene_no:03d}-{scene.scene_id}.md"
                    self.file_repository.write_text(file_path, draft.content_md)
                    items.append(f"markdown/scenes/{chapter.chapter_no:04d}-{scene.scene_no:03d}-{scene.scene_id}.md")

        return items

    def _classify_project_package_file(self, relative_path: str) -> str:
        if relative_path.startswith("canonical/"):
            return "canonical"
        if relative_path.startswith("derived/"):
            return "derived"
        if relative_path.startswith("memory/"):
            return "memory"
        if relative_path.startswith("checks/"):
            return "checks"
        if relative_path.startswith("markdown/"):
            return "markdown"
        return "unknown"

    def _sha256(self, path: Path) -> str:
        digest = hashlib.sha256()
        digest.update(path.read_bytes())
        return digest.hexdigest()
