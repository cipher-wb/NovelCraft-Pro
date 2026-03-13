from __future__ import annotations

import uuid
from datetime import datetime
from pathlib import Path

from backend.app.core.paths import AppPaths
from backend.app.domain.models.common import utc_now
from backend.app.domain.models.issues import ChapterCheckReport, ChapterCheckSourceVersions, CheckRuleSummary, ConsistencyIssue
from backend.app.domain.models.planning import ChapterPlan
from backend.app.domain.models.writing import ChapterAssembledDocument, SceneDraft
from backend.app.repositories.file_repository import FileRepository
from backend.app.repositories.sqlite_repository import SQLiteRepository
from backend.app.services.planner_service import PlannerService
from backend.app.services.scene_draft_service import SceneDraftService


class ChapterChecksService:
    def __init__(
        self,
        paths: AppPaths,
        file_repository: FileRepository,
        sqlite_repository: SQLiteRepository,
        planner_service: PlannerService,
        draft_service: SceneDraftService,
    ) -> None:
        self.paths = paths
        self.file_repository = file_repository
        self.sqlite_repository = sqlite_repository
        self.planner_service = planner_service
        self.draft_service = draft_service

    def get_latest_report(self, project_id: str, chapter_id: str) -> ChapterCheckReport | None:
        slug = self._require_project(project_id)["slug"]
        path = self.paths.chapter_check_latest_path(slug, chapter_id)
        if not self.file_repository.exists(path):
            return None
        return ChapterCheckReport.model_validate(self.file_repository.read_json(path))

    def run_for_chapter(self, project_id: str, assembled: ChapterAssembledDocument, trigger: str) -> ChapterCheckReport:
        slug = self._require_project(project_id)["slug"]
        chapter = self.planner_service.get_chapter(project_id, assembled.chapter_id)
        scene_plans = self.planner_service.list_scenes(project_id, assembled.chapter_id)
        try:
            issues = self._evaluate_rules(project_id, chapter, scene_plans, assembled)
            report = self._build_report(assembled, trigger, issues)
        except Exception:
            report = ChapterCheckReport(
                report_id=f"chapter_check_{uuid.uuid4().hex[:12]}",
                project_id=assembled.project_id,
                volume_id=assembled.volume_id,
                chapter_id=assembled.chapter_id,
                trigger=trigger,
                created_at=utc_now(),
                source_versions=self._source_versions(assembled),
                overall_status="error",
                blocker_count=0,
                warning_count=0,
                issues=[],
                rule_summaries=[CheckRuleSummary(rule_family="chapter_checks", status="error", issue_count=0)],
            )
        self._write_report(slug, assembled.chapter_id, report)
        assembled.latest_check_report_path = self.paths.relative_to_project(slug, self.paths.chapter_check_latest_path(slug, assembled.chapter_id))
        assembled.last_check_status = report.overall_status
        assembled.last_check_blocker_count = report.blocker_count
        assembled.last_check_warning_count = report.warning_count
        self.file_repository.write_json(self.paths.chapter_assembled_path(slug, assembled.chapter_id), assembled.model_dump(mode="json"))
        return report

    def ensure_finalize_allowed(self, project_id: str, assembled: ChapterAssembledDocument) -> ChapterCheckReport:
        return self.run_for_chapter(project_id, assembled, trigger="finalize_preflight")

    def _evaluate_rules(
        self,
        project_id: str,
        chapter: ChapterPlan,
        scene_plans: list,
        assembled: ChapterAssembledDocument,
    ) -> list[ConsistencyIssue]:
        issues: list[ConsistencyIssue] = []
        checker_run_id = f"chapter_check_{uuid.uuid4().hex[:12]}"
        detected_at = utc_now()
        accepted_by_scene, duplicate_scene_ids = self._accepted_drafts_for_chapter(project_id, chapter.chapter_id)

        for scene in scene_plans:
            if scene.scene_id in duplicate_scene_ids:
                issues.append(
                    self._issue(
                        project_id,
                        checker_run_id,
                        detected_at,
                        "chapter.scene.accepted.duplicate",
                        "blocker",
                        chapter.chapter_id,
                        f"场景 {scene.scene_id} 存在多个 accepted draft",
                    )
                )
            elif scene.scene_id not in accepted_by_scene:
                issues.append(
                    self._issue(
                        project_id,
                        checker_run_id,
                        detected_at,
                        "chapter.scene.accepted.missing",
                        "blocker",
                        chapter.chapter_id,
                        f"场景 {scene.scene_id} 缺少唯一 active accepted draft",
                    )
                )

        expected_order = [(scene.scene_id, scene.scene_no) for scene in sorted(scene_plans, key=lambda item: item.scene_no)]
        assembled_order = [(item.scene_id, item.scene_no) for item in assembled.scene_order]
        if assembled_order != expected_order:
            issues.append(
                self._issue(
                    project_id,
                    checker_run_id,
                    detected_at,
                    "chapter.scene.order.invalid",
                    "blocker",
                    chapter.chapter_id,
                    "assembled scene_order 与 chapter plan 顺序不一致。",
                )
            )

        if not assembled.content_md.strip():
            issues.append(
                self._issue(
                    project_id,
                    checker_run_id,
                    detected_at,
                    "chapter.content.empty",
                    "blocker",
                    chapter.chapter_id,
                    "章节 assembled 内容为空。",
                )
            )

        for scene in scene_plans:
            draft = accepted_by_scene.get(scene.scene_id)
            if draft is None:
                continue
            trimmed = draft.content_md.strip()
            if trimmed and trimmed not in assembled.content_md:
                issues.append(
                    self._issue(
                        project_id,
                        checker_run_id,
                        detected_at,
                        "chapter.scene.content.missing",
                        "blocker",
                        chapter.chapter_id,
                        f"已接受场景 {scene.scene_id} 的正文未完整进入 chapter assembled 内容。",
                    )
                )

        if not assembled.summary.strip():
            issues.append(
                self._issue(
                    project_id,
                    checker_run_id,
                    detected_at,
                    "chapter.summary.missing",
                    "warning",
                    chapter.chapter_id,
                    "章节 summary 为空。",
                )
            )

        if not assembled.hook.strip():
            issues.append(
                self._issue(
                    project_id,
                    checker_run_id,
                    detected_at,
                    "chapter.hook.missing",
                    "warning",
                    chapter.chapter_id,
                    "章节 hook 为空。",
                )
            )

        if assembled.basic_stats.char_count < 50:
            issues.append(
                self._issue(
                    project_id,
                    checker_run_id,
                    detected_at,
                    "chapter.content.too_short",
                    "warning",
                    chapter.chapter_id,
                    "章节 assembled 内容过短。",
                )
            )
        return issues

    def _build_report(self, assembled: ChapterAssembledDocument, trigger: str, issues: list[ConsistencyIssue]) -> ChapterCheckReport:
        blocker_count = sum(1 for issue in issues if issue.severity == "blocker")
        warning_count = sum(1 for issue in issues if issue.severity == "warning")
        if blocker_count > 0:
            overall_status = "blocked"
        elif warning_count > 0:
            overall_status = "warning"
        else:
            overall_status = "clean"
        return ChapterCheckReport(
            report_id=f"chapter_check_{uuid.uuid4().hex[:12]}",
            project_id=assembled.project_id,
            volume_id=assembled.volume_id,
            chapter_id=assembled.chapter_id,
            trigger=trigger,
            created_at=utc_now(),
            source_versions=self._source_versions(assembled),
            overall_status=overall_status,
            blocker_count=blocker_count,
            warning_count=warning_count,
            issues=issues,
            rule_summaries=[
                CheckRuleSummary(rule_family="chapter_assembly", status=overall_status, issue_count=len(issues))
            ],
        )

    def _source_versions(self, assembled: ChapterAssembledDocument) -> ChapterCheckSourceVersions:
        return ChapterCheckSourceVersions(
            volume_version=assembled.source_versions.volume_version,
            chapter_version=assembled.source_versions.chapter_version,
            scene_versions=dict(assembled.source_versions.scene_versions),
            accepted_draft_ids=dict(assembled.source_versions.accepted_draft_ids),
            assembled_version=assembled.version,
        )

    def _write_report(self, slug: str, chapter_id: str, report: ChapterCheckReport) -> None:
        self.file_repository.write_json(self.paths.chapter_check_latest_path(slug, chapter_id), report.model_dump(mode="json"))

    def _accepted_drafts_for_chapter(self, project_id: str, chapter_id: str) -> tuple[dict[str, SceneDraft], set[str]]:
        chapter = self.planner_service.get_chapter(project_id, chapter_id)
        scenes = self.planner_service.list_scenes(project_id, chapter_id)
        project = self._require_project(project_id)
        slug = project["slug"]
        accepted: dict[str, SceneDraft] = {}
        duplicates: set[str] = set()
        for scene in scenes:
            scene_dir = self.paths.scene_drafts_dir(slug, scene.scene_id)
            if not scene_dir.exists():
                continue
            accepted_drafts = []
            for draft_path in sorted(scene_dir.glob("draft-*.json")):
                draft = SceneDraft.model_validate(self.file_repository.read_json(draft_path))
                if draft.status == "accepted":
                    accepted_drafts.append(draft)
            if len(accepted_drafts) == 1:
                accepted[scene.scene_id] = accepted_drafts[0]
            elif len(accepted_drafts) > 1:
                duplicates.add(scene.scene_id)
        return accepted, duplicates

    def _issue(
        self,
        project_id: str,
        checker_run_id: str,
        detected_at: datetime,
        rule_id: str,
        severity: str,
        chapter_id: str,
        description: str,
    ) -> ConsistencyIssue:
        return ConsistencyIssue(
            issue_id=f"issue_{uuid.uuid4().hex[:12]}",
            project_id=project_id,
            issue_type="chapter_assembly",
            rule_id=rule_id,
            severity=severity,
            status="open",
            source_scope="chapter",
            source_id=chapter_id,
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
