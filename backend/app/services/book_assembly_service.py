from __future__ import annotations

from typing import Any

from backend.app.core.paths import AppPaths
from backend.app.domain.models.common import utc_now
from backend.app.domain.models.issues import BookCheckReport
from backend.app.domain.models.planning import MasterOutlineDocument, VolumePlan
from backend.app.domain.models.writing import (
    BookAssembledDocument,
    BookAssembledSourceVersions,
    BookProgressStats,
    BookVolumeOrderItem,
    VolumeAssembledDocument,
)
from backend.app.repositories.file_repository import FileRepository
from backend.app.repositories.sqlite_repository import SQLiteRepository
from backend.app.services.book_checks_service import BookChecksService
from backend.app.services.exceptions import ConflictError
from backend.app.services.memory_service import MemoryService
from backend.app.services.planner_service import PlannerService


class BookAssemblyService:
    def __init__(
        self,
        paths: AppPaths,
        file_repository: FileRepository,
        sqlite_repository: SQLiteRepository,
        planner_service: PlannerService,
        volume_assembly_service,
        memory_service: MemoryService,
        book_checks_service: BookChecksService,
    ) -> None:
        self.paths = paths
        self.file_repository = file_repository
        self.sqlite_repository = sqlite_repository
        self.planner_service = planner_service
        self.volume_assembly_service = volume_assembly_service
        self.memory_service = memory_service
        self.book_checks_service = book_checks_service

    def assemble(self, project_id: str) -> BookAssembledDocument:
        project = self._require_project(project_id)
        slug = project["slug"]
        outline, planned_volumes = self._load_planned_volumes(project_id)
        finalized_volumes = self._load_finalized_volumes(slug, planned_volumes)
        if not finalized_volumes:
            raise ConflictError("At least one finalized volume is required before assembling book.")

        content_md = "\n\n".join(artifact.content_md.strip() for _, artifact in finalized_volumes)
        existing = self._read_assembled(slug)
        next_version = 1 if existing is None else existing.version + 1
        assembled = BookAssembledDocument(
            project_id=project_id,
            version=next_version,
            status="assembled",
            updated_at=utc_now(),
            source_versions=BookAssembledSourceVersions(
                master_outline_version=outline.version,
                planned_volume_versions={volume.volume_id: volume.version for volume in planned_volumes},
                finalized_volume_versions={volume.volume_id: artifact.version for volume, artifact in finalized_volumes},
            ),
            planned_volume_order=[volume.volume_id for volume in planned_volumes],
            volume_order=[
                BookVolumeOrderItem(volume_id=volume.volume_id, volume_no=volume.volume_no, assembled_version=artifact.version)
                for volume, artifact in finalized_volumes
            ],
            content_md=content_md,
            summary=self._build_summary(finalized_volumes),
            hook=self._build_hook(finalized_volumes),
            progress_stats=self._build_progress_stats(planned_volumes, finalized_volumes),
            latest_check_report_path=self.paths.relative_to_project(slug, self.paths.book_check_latest_path(slug)),
            last_check_status=None,
            last_check_blocker_count=0,
            last_check_warning_count=0,
            finalized_at=None,
            finalized_from_assembly_version=None,
        )
        self._write_assembled(slug, assembled)
        self.book_checks_service.run_for_book(project_id, assembled, trigger="assemble_auto")
        return self.get_assembled(project_id)

    def get_assembled(self, project_id: str) -> BookAssembledDocument:
        project = self._require_project(project_id)
        slug = project["slug"]
        assembled = self._read_assembled(slug)
        if assembled is None:
            raise KeyError(project_id)
        return self._refresh_stale_status(project_id, slug, assembled)

    def recheck(self, project_id: str) -> BookCheckReport:
        assembled = self.get_assembled(project_id)
        return self.book_checks_service.run_for_book(project_id, assembled, trigger="manual_recheck")

    def get_latest_report(self, project_id: str) -> BookCheckReport | None:
        return self.book_checks_service.get_latest_report(project_id)

    def finalize(self, project_id: str) -> BookAssembledDocument:
        project = self._require_project(project_id)
        slug = project["slug"]
        assembled = self.get_assembled(project_id)
        if assembled.status == "stale":
            raise ConflictError("Stale book must be re-assembled before finalize.")
        if assembled.status == "finalized":
            return assembled

        report = self.book_checks_service.ensure_finalize_allowed(project_id, assembled)
        assembled = self.get_assembled(project_id)
        if report.overall_status in {"blocked", "error"}:
            raise ConflictError("Book finalize blocked by latest book checks.")
        if assembled.status == "stale":
            raise ConflictError("Stale book must be re-assembled before finalize.")

        assembled.status = "finalized"
        assembled.finalized_at = utc_now()
        assembled.finalized_from_assembly_version = assembled.version
        self._write_assembled(slug, assembled)
        self.memory_service.update_finalized_book_summary(slug, assembled)
        return self.get_assembled(project_id)

    def _load_planned_volumes(self, project_id: str) -> tuple[MasterOutlineDocument, list[VolumePlan]]:
        outline = self.planner_service.get_master_outline(project_id)
        planned_volumes = sorted(self.planner_service.list_volumes(project_id), key=lambda item: item.volume_no)
        return outline, planned_volumes

    def _load_finalized_volumes(self, slug: str, planned_volumes: list[VolumePlan]) -> list[tuple[VolumePlan, VolumeAssembledDocument]]:
        finalized: list[tuple[VolumePlan, VolumeAssembledDocument]] = []
        for volume in planned_volumes:
            path = self.paths.volume_assembled_path(slug, volume.volume_id)
            if not self.file_repository.exists(path):
                continue
            try:
                artifact = VolumeAssembledDocument.model_validate(self.file_repository.read_json(path))
            except Exception as error:
                raise ConflictError(f"Volume artifact for {volume.volume_id} is invalid.") from error
            if artifact.status != "finalized":
                continue
            if artifact.version <= 0:
                raise ConflictError(f"Finalized volume artifact for {volume.volume_id} has invalid assembled version.")
            finalized.append((volume, artifact))
        return finalized

    def _build_summary(self, finalized_volumes: list[tuple[VolumePlan, VolumeAssembledDocument]]) -> str:
        parts: list[str] = []
        for volume, artifact in finalized_volumes[:5]:
            piece = artifact.summary.strip() or artifact.hook.strip() or self._non_whitespace_prefix(artifact.content_md, 160)
            if piece:
                parts.append(f"第{volume.volume_no}卷：{piece}")
        return " ".join(parts).strip()

    def _build_hook(self, finalized_volumes: list[tuple[VolumePlan, VolumeAssembledDocument]]) -> str:
        _, last_artifact = finalized_volumes[-1]
        return last_artifact.hook.strip() or last_artifact.summary.strip()

    def _build_progress_stats(
        self,
        planned_volumes: list[VolumePlan],
        finalized_volumes: list[tuple[VolumePlan, VolumeAssembledDocument]],
    ) -> BookProgressStats:
        planned_count = len(planned_volumes)
        finalized_count = len(finalized_volumes)
        volume_nos = [volume.volume_no for volume, _ in finalized_volumes]
        return BookProgressStats(
            planned_volume_count=planned_count,
            finalized_volume_count=finalized_count,
            completion_ratio=(finalized_count / planned_count) if planned_count else 0.0,
            chapter_count_total=sum(artifact.progress_stats.finalized_chapter_count for _, artifact in finalized_volumes),
            scene_count_total=sum(artifact.progress_stats.scene_count_total for _, artifact in finalized_volumes),
            paragraph_count_total=sum(artifact.progress_stats.paragraph_count_total for _, artifact in finalized_volumes),
            char_count_total=sum(artifact.progress_stats.char_count_total for _, artifact in finalized_volumes),
            first_finalized_volume_no=min(volume_nos) if volume_nos else None,
            last_finalized_volume_no=max(volume_nos) if volume_nos else None,
        )

    def _refresh_stale_status(self, project_id: str, slug: str, assembled: BookAssembledDocument) -> BookAssembledDocument:
        outline, planned_volumes = self._load_planned_volumes(project_id)
        finalized_volumes = self._load_finalized_volumes(slug, planned_volumes)
        stale = False
        if outline.version != assembled.source_versions.master_outline_version:
            stale = True
        planned_order = [volume.volume_id for volume in planned_volumes]
        if planned_order != assembled.planned_volume_order:
            stale = True
        planned_versions = {volume.volume_id: volume.version for volume in planned_volumes}
        if planned_versions != assembled.source_versions.planned_volume_versions:
            stale = True
        finalized_versions = {volume.volume_id: artifact.version for volume, artifact in finalized_volumes}
        if finalized_versions != assembled.source_versions.finalized_volume_versions:
            stale = True
        current_order = [(volume.volume_id, volume.volume_no, artifact.version) for volume, artifact in finalized_volumes]
        stored_order = [(item.volume_id, item.volume_no, item.assembled_version) for item in assembled.volume_order]
        if current_order != stored_order:
            stale = True
        if stale and assembled.status != "stale":
            assembled.status = "stale"
            assembled.updated_at = utc_now()
            self._write_assembled(slug, assembled)
        return assembled

    def _non_whitespace_prefix(self, content_md: str, limit: int) -> str:
        return "".join(content_md.split())[:limit]

    def _read_assembled(self, slug: str) -> BookAssembledDocument | None:
        path = self.paths.book_assembled_path(slug)
        if not self.file_repository.exists(path):
            return None
        return BookAssembledDocument.model_validate(self.file_repository.read_json(path))

    def _write_assembled(self, slug: str, assembled: BookAssembledDocument) -> None:
        self.file_repository.write_json(self.paths.book_assembled_path(slug), assembled.model_dump(mode="json"))

    def _require_project(self, project_id: str) -> dict[str, Any]:
        project = self.sqlite_repository.get_project_record(project_id)
        if project is None:
            raise KeyError(project_id)
        return project
