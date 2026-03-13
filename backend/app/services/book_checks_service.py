from __future__ import annotations

import uuid
from datetime import datetime

from backend.app.core.paths import AppPaths
from backend.app.domain.models.common import utc_now
from backend.app.domain.models.issues import BookCheckReport, BookCheckSourceVersions, CheckRuleSummary, ConsistencyIssue
from backend.app.domain.models.writing import BookAssembledDocument, VolumeAssembledDocument
from backend.app.repositories.file_repository import FileRepository
from backend.app.repositories.sqlite_repository import SQLiteRepository
from backend.app.services.exceptions import ConflictError
from backend.app.services.planner_service import PlannerService


class BookChecksService:
    TOO_SHORT_CHAR_THRESHOLD = 100

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

    def get_latest_report(self, project_id: str) -> BookCheckReport | None:
        slug = self._require_project(project_id)["slug"]
        path = self.paths.book_check_latest_path(slug)
        if not self.file_repository.exists(path):
            return None
        return BookCheckReport.model_validate(self.file_repository.read_json(path))

    def run_for_book(self, project_id: str, assembled: BookAssembledDocument, trigger: str) -> BookCheckReport:
        slug = self._require_project(project_id)["slug"]
        try:
            issues = self._evaluate_rules(project_id, assembled)
            report = self._build_report(assembled, trigger, issues)
        except Exception:
            report = BookCheckReport(
                report_id=f"book_check_{uuid.uuid4().hex[:12]}",
                project_id=assembled.project_id,
                trigger=trigger,
                created_at=utc_now(),
                source_versions=self._source_versions(assembled),
                overall_status="error",
                blocker_count=0,
                warning_count=0,
                issues=[],
                rule_summaries=[CheckRuleSummary(rule_family="book_assembly", status="error", issue_count=0)],
            )
        self._write_report(slug, report)
        assembled.latest_check_report_path = self.paths.relative_to_project(slug, self.paths.book_check_latest_path(slug))
        assembled.last_check_status = report.overall_status
        assembled.last_check_blocker_count = report.blocker_count
        assembled.last_check_warning_count = report.warning_count
        self.file_repository.write_json(self.paths.book_assembled_path(slug), assembled.model_dump(mode="json"))
        return report

    def ensure_finalize_allowed(self, project_id: str, assembled: BookAssembledDocument) -> BookCheckReport:
        return self.run_for_book(project_id, assembled, trigger="finalize_preflight")

    def _evaluate_rules(self, project_id: str, assembled: BookAssembledDocument) -> list[ConsistencyIssue]:
        planned_volumes = self.planner_service.list_volumes(project_id)
        checker_run_id = f"book_check_{uuid.uuid4().hex[:12]}"
        detected_at = utc_now()
        issues: list[ConsistencyIssue] = []

        current_planned_ids = [volume.volume_id for volume in planned_volumes]
        current_finalized = self._current_finalized_volumes(project_id)
        current_finalized_ids = [volume.volume_id for volume, _ in current_finalized]

        for volume in planned_volumes:
            if volume.volume_id not in current_finalized_ids:
                issues.append(
                    self._issue(
                        project_id,
                        checker_run_id,
                        detected_at,
                        "book.volume.finalized.missing",
                        "blocker",
                        f"卷 {volume.volume_id} 尚未 finalized，book 不能 finalize。",
                    )
                )

        expected_order = [(volume.volume_id, volume.volume_no) for volume, _ in current_finalized]
        assembled_order = [(item.volume_id, item.volume_no) for item in assembled.volume_order]
        if assembled.planned_volume_order != current_planned_ids or assembled_order != expected_order:
            issues.append(
                self._issue(
                    project_id,
                    checker_run_id,
                    detected_at,
                    "book.volume.order.invalid",
                    "blocker",
                    "book assembled 的 volume 顺序与当前 canonical 顺序不一致。",
                )
            )

        if not assembled.content_md.strip():
            issues.append(
                self._issue(
                    project_id,
                    checker_run_id,
                    detected_at,
                    "book.content.empty",
                    "blocker",
                    "book assembled 内容为空。",
                )
            )

        finalized_by_id = {volume.volume_id: artifact for volume, artifact in current_finalized}
        for item in assembled.volume_order:
            artifact = finalized_by_id.get(item.volume_id)
            if artifact is None:
                continue
            trimmed = artifact.content_md.strip()
            if trimmed and trimmed not in assembled.content_md:
                issues.append(
                    self._issue(
                        project_id,
                        checker_run_id,
                        detected_at,
                        "book.volume.content.missing",
                        "blocker",
                        f"已 finalized 的卷 {item.volume_id} 正文未完整进入 book assembled 内容。",
                    )
                )

        if not assembled.summary.strip():
            issues.append(
                self._issue(
                    project_id,
                    checker_run_id,
                    detected_at,
                    "book.summary.missing",
                    "warning",
                    "book summary 为空。",
                )
            )

        if not assembled.hook.strip():
            issues.append(
                self._issue(
                    project_id,
                    checker_run_id,
                    detected_at,
                    "book.hook.missing",
                    "warning",
                    "book hook 为空。",
                )
            )

        if assembled.progress_stats.char_count_total < self.TOO_SHORT_CHAR_THRESHOLD:
            issues.append(
                self._issue(
                    project_id,
                    checker_run_id,
                    detected_at,
                    "book.content.too_short",
                    "warning",
                    "book assembled 内容过短。",
                )
            )

        return issues

    def _current_finalized_volumes(self, project_id: str) -> list[tuple]:
        planned_volumes = self.planner_service.list_volumes(project_id)
        slug = self._require_project(project_id)["slug"]
        finalized: list[tuple] = []
        for volume in planned_volumes:
            path = self.paths.volume_assembled_path(slug, volume.volume_id)
            if not self.file_repository.exists(path):
                continue
            try:
                artifact = VolumeAssembledDocument.model_validate(self.file_repository.read_json(path))
            except Exception as error:
                raise ConflictError(f"Volume artifact for {volume.volume_id} is invalid.") from error
            if artifact.status == "finalized":
                finalized.append((volume, artifact))
        return finalized

    def _build_report(self, assembled: BookAssembledDocument, trigger: str, issues: list[ConsistencyIssue]) -> BookCheckReport:
        blocker_count = sum(1 for issue in issues if issue.severity == "blocker")
        warning_count = sum(1 for issue in issues if issue.severity == "warning")
        if blocker_count > 0:
            overall_status = "blocked"
        elif warning_count > 0:
            overall_status = "warning"
        else:
            overall_status = "clean"
        return BookCheckReport(
            report_id=f"book_check_{uuid.uuid4().hex[:12]}",
            project_id=assembled.project_id,
            trigger=trigger,
            created_at=utc_now(),
            source_versions=self._source_versions(assembled),
            overall_status=overall_status,
            blocker_count=blocker_count,
            warning_count=warning_count,
            issues=issues,
            rule_summaries=[CheckRuleSummary(rule_family="book_assembly", status=overall_status, issue_count=len(issues))],
        )

    def _source_versions(self, assembled: BookAssembledDocument) -> BookCheckSourceVersions:
        return BookCheckSourceVersions(
            master_outline_version=assembled.source_versions.master_outline_version,
            planned_volume_versions=dict(assembled.source_versions.planned_volume_versions),
            finalized_volume_versions=dict(assembled.source_versions.finalized_volume_versions),
            assembled_version=assembled.version,
        )

    def _write_report(self, slug: str, report: BookCheckReport) -> None:
        self.file_repository.write_json(self.paths.book_check_latest_path(slug), report.model_dump(mode="json"))

    def _issue(
        self,
        project_id: str,
        checker_run_id: str,
        detected_at: datetime,
        rule_id: str,
        severity: str,
        description: str,
    ) -> ConsistencyIssue:
        return ConsistencyIssue(
            issue_id=f"issue_{uuid.uuid4().hex[:12]}",
            project_id=project_id,
            issue_type="book_assembly",
            rule_id=rule_id,
            severity=severity,
            status="open",
            source_scope="project",
            source_id=project_id,
            title=rule_id,
            description=description,
            checker_run_id=checker_run_id,
            detected_at=detected_at,
        )

    def _require_project(self, project_id: str) -> dict:
        project = self.sqlite_repository.get_project_record(project_id)
        if project is None:
            raise KeyError(project_id)
        return project
