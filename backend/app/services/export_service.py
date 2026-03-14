from __future__ import annotations

import uuid
from pathlib import Path
from typing import Any

from backend.app.core.paths import AppPaths
from backend.app.domain.models.common import utc_now
from backend.app.domain.models.writing import (
    BookAssembledDocument,
    ExportPackageManifest,
    ExportResult,
    SceneDraft,
    VolumeAssembledDocument,
    ChapterAssembledDocument,
)
from backend.app.repositories.file_repository import FileRepository
from backend.app.repositories.sqlite_repository import SQLiteRepository
from backend.app.services.exceptions import ConflictError
from backend.app.services.planner_service import PlannerService


class ExportService:
    SUPPORTED_SCOPES = {"scene", "chapter", "volume", "book"}
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
        if not resolved_target_id:
            raise ValueError("target_id is required for this export scope.")

        export_id = self._new_export_id()
        created_at = utc_now()
        warnings: list[str] = []

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
