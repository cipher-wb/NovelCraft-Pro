from __future__ import annotations

import uuid
from datetime import datetime

from backend.app.core.paths import AppPaths
from backend.app.domain.models.common import utc_now
from backend.app.domain.models.issues import CheckRuleSummary, ConsistencyIssue, VolumeCheckReport, VolumeCheckSourceVersions
from backend.app.domain.models.writing import ChapterAssembledDocument, VolumeAssembledDocument
from backend.app.repositories.file_repository import FileRepository
from backend.app.repositories.sqlite_repository import SQLiteRepository
from backend.app.services.exceptions import ConflictError
from backend.app.services.planner_service import PlannerService


class VolumeChecksService:
    TOO_SHORT_CHAR_THRESHOLD = 200

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

    def get_latest_report(self, project_id: str, volume_id: str) -> VolumeCheckReport | None:
        slug = self._require_project(project_id)["slug"]
        path = self.paths.volume_check_latest_path(slug, volume_id)
        if not self.file_repository.exists(path):
            return None
        return VolumeCheckReport.model_validate(self.file_repository.read_json(path))

    def run_for_volume(self, project_id: str, assembled: VolumeAssembledDocument, trigger: str) -> VolumeCheckReport:
        slug = self._require_project(project_id)["slug"]
        try:
            issues = self._evaluate_rules(project_id, assembled)
            report = self._build_report(assembled, trigger, issues)
        except Exception:
            report = VolumeCheckReport(
                report_id=f"volume_check_{uuid.uuid4().hex[:12]}",
                project_id=assembled.project_id,
                volume_id=assembled.volume_id,
                trigger=trigger,
                created_at=utc_now(),
                source_versions=self._source_versions(assembled),
                overall_status="error",
                blocker_count=0,
                warning_count=0,
                issues=[],
                rule_summaries=[CheckRuleSummary(rule_family="volume_assembly", status="error", issue_count=0)],
            )
        self._write_report(slug, assembled.volume_id, report)
        assembled.latest_check_report_path = self.paths.relative_to_project(slug, self.paths.volume_check_latest_path(slug, assembled.volume_id))
        assembled.last_check_status = report.overall_status
        assembled.last_check_blocker_count = report.blocker_count
        assembled.last_check_warning_count = report.warning_count
        self.file_repository.write_json(self.paths.volume_assembled_path(slug, assembled.volume_id), assembled.model_dump(mode="json"))
        return report

    def ensure_finalize_allowed(self, project_id: str, assembled: VolumeAssembledDocument) -> VolumeCheckReport:
        return self.run_for_volume(project_id, assembled, trigger="finalize_preflight")

    def _evaluate_rules(self, project_id: str, assembled: VolumeAssembledDocument) -> list[ConsistencyIssue]:
        planned_chapters = self.planner_service.list_chapters(project_id, assembled.volume_id)
        checker_run_id = f"volume_check_{uuid.uuid4().hex[:12]}"
        detected_at = utc_now()
        issues: list[ConsistencyIssue] = []

        current_planned_ids = [chapter.chapter_id for chapter in planned_chapters]
        current_finalized = self._current_finalized_chapters(project_id, assembled.volume_id)
        current_finalized_ids = [chapter.chapter_id for chapter, _ in current_finalized]

        for chapter in planned_chapters:
            if chapter.chapter_id not in current_finalized_ids:
                issues.append(
                    self._issue(
                        project_id,
                        checker_run_id,
                        detected_at,
                        "volume.chapter.finalized.missing",
                        "blocker",
                        assembled.volume_id,
                        f"章节 {chapter.chapter_id} 尚未 finalized，volume 不能 finalize。",
                    )
                )

        expected_order = [(chapter.chapter_id, chapter.chapter_no) for chapter, _ in current_finalized]
        assembled_order = [(item.chapter_id, item.chapter_no) for item in assembled.chapter_order]
        if assembled.planned_chapter_order != current_planned_ids or assembled_order != expected_order:
            issues.append(
                self._issue(
                    project_id,
                    checker_run_id,
                    detected_at,
                    "volume.chapter.order.invalid",
                    "blocker",
                    assembled.volume_id,
                    "volume assembled 的 chapter 顺序与当前 canonical 顺序不一致。",
                )
            )

        if not assembled.content_md.strip():
            issues.append(
                self._issue(
                    project_id,
                    checker_run_id,
                    detected_at,
                    "volume.content.empty",
                    "blocker",
                    assembled.volume_id,
                    "volume assembled 内容为空。",
                )
            )

        finalized_by_id = {chapter.chapter_id: artifact for chapter, artifact in current_finalized}
        for item in assembled.chapter_order:
            artifact = finalized_by_id.get(item.chapter_id)
            if artifact is None:
                continue
            trimmed = artifact.content_md.strip()
            if trimmed and trimmed not in assembled.content_md:
                issues.append(
                    self._issue(
                        project_id,
                        checker_run_id,
                        detected_at,
                        "volume.chapter.content.missing",
                        "blocker",
                        assembled.volume_id,
                        f"已 finalized 的章节 {item.chapter_id} 正文未完整进入 volume assembled 内容。",
                    )
                )

        if not assembled.summary.strip():
            issues.append(
                self._issue(
                    project_id,
                    checker_run_id,
                    detected_at,
                    "volume.summary.missing",
                    "warning",
                    assembled.volume_id,
                    "volume summary 为空。",
                )
            )

        if not assembled.hook.strip():
            issues.append(
                self._issue(
                    project_id,
                    checker_run_id,
                    detected_at,
                    "volume.hook.missing",
                    "warning",
                    assembled.volume_id,
                    "volume hook 为空。",
                )
            )

        if assembled.progress_stats.char_count_total < self.TOO_SHORT_CHAR_THRESHOLD:
            issues.append(
                self._issue(
                    project_id,
                    checker_run_id,
                    detected_at,
                    "volume.content.too_short",
                    "warning",
                    assembled.volume_id,
                    "volume assembled 内容过短。",
                )
            )
        return issues

    def _current_finalized_chapters(self, project_id: str, volume_id: str) -> list[tuple]:
        planned_chapters = self.planner_service.list_chapters(project_id, volume_id)
        slug = self._require_project(project_id)["slug"]
        finalized: list[tuple] = []
        for chapter in planned_chapters:
            path = self.paths.chapter_assembled_path(slug, chapter.chapter_id)
            if not self.file_repository.exists(path):
                continue
            try:
                artifact = ChapterAssembledDocument.model_validate(self.file_repository.read_json(path))
            except Exception as error:
                raise ConflictError(f"Chapter artifact for {chapter.chapter_id} is invalid.") from error
            if artifact.status == "finalized":
                finalized.append((chapter, artifact))
        return finalized

    def _build_report(self, assembled: VolumeAssembledDocument, trigger: str, issues: list[ConsistencyIssue]) -> VolumeCheckReport:
        blocker_count = sum(1 for issue in issues if issue.severity == "blocker")
        warning_count = sum(1 for issue in issues if issue.severity == "warning")
        if blocker_count > 0:
            overall_status = "blocked"
        elif warning_count > 0:
            overall_status = "warning"
        else:
            overall_status = "clean"
        return VolumeCheckReport(
            report_id=f"volume_check_{uuid.uuid4().hex[:12]}",
            project_id=assembled.project_id,
            volume_id=assembled.volume_id,
            trigger=trigger,
            created_at=utc_now(),
            source_versions=self._source_versions(assembled),
            overall_status=overall_status,
            blocker_count=blocker_count,
            warning_count=warning_count,
            issues=issues,
            rule_summaries=[CheckRuleSummary(rule_family="volume_assembly", status=overall_status, issue_count=len(issues))],
        )

    def _source_versions(self, assembled: VolumeAssembledDocument) -> VolumeCheckSourceVersions:
        return VolumeCheckSourceVersions(
            volume_version=assembled.source_versions.volume_version,
            planned_chapter_versions=dict(assembled.source_versions.planned_chapter_versions),
            finalized_chapter_versions=dict(assembled.source_versions.finalized_chapter_versions),
            assembled_version=assembled.version,
        )

    def _write_report(self, slug: str, volume_id: str, report: VolumeCheckReport) -> None:
        self.file_repository.write_json(self.paths.volume_check_latest_path(slug, volume_id), report.model_dump(mode="json"))

    def _issue(
        self,
        project_id: str,
        checker_run_id: str,
        detected_at: datetime,
        rule_id: str,
        severity: str,
        volume_id: str,
        description: str,
    ) -> ConsistencyIssue:
        return ConsistencyIssue(
            issue_id=f"issue_{uuid.uuid4().hex[:12]}",
            project_id=project_id,
            issue_type="volume_assembly",
            rule_id=rule_id,
            severity=severity,
            status="open",
            source_scope="volume",
            source_id=volume_id,
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
