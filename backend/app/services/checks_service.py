from __future__ import annotations

import uuid
from typing import Any

from backend.app.core.paths import AppPaths
from backend.app.domain.models.common import utc_now
from backend.app.domain.models.issues import CheckRuleSummary, CheckSourceVersions, SceneDraftCheckReport
from backend.app.domain.models.writing import ContextBundle, SceneDraft
from backend.app.repositories.file_repository import FileRepository
from backend.app.repositories.sqlite_repository import SQLiteRepository
from backend.app.services.bible_service import BibleService
from backend.app.services.check_rule_evaluators import (
    CharacterConsistencyEvaluator,
    CheckInputContext,
    SceneAlignmentEvaluator,
    TimelineOrderEvaluator,
    WorldPowerConflictEvaluator,
)
from backend.app.services.context_bundle_service import ContextBundleService
from backend.app.services.exceptions import ConflictError
from backend.app.services.planner_service import PlannerService


class ChecksService:
    def __init__(
        self,
        paths: AppPaths,
        file_repository: FileRepository,
        sqlite_repository: SQLiteRepository,
        bible_service: BibleService,
        planner_service: PlannerService,
        context_bundle_service: ContextBundleService,
    ) -> None:
        self.paths = paths
        self.file_repository = file_repository
        self.sqlite_repository = sqlite_repository
        self.bible_service = bible_service
        self.planner_service = planner_service
        self.context_bundle_service = context_bundle_service
        self.evaluators = [
            SceneAlignmentEvaluator(),
            CharacterConsistencyEvaluator(),
            TimelineOrderEvaluator(),
            WorldPowerConflictEvaluator(),
        ]

    def run_for_draft(self, project_id: str, draft_id: str, trigger: str) -> SceneDraftCheckReport:
        slug = self._require_project(project_id)["slug"]
        draft = self._load_draft(project_id, draft_id)
        aggregate = self.bible_service.get_bible_aggregate(project_id)
        scene = self.planner_service.get_scene(project_id, draft.scene_id)
        chapter = self.planner_service.get_chapter(project_id, draft.chapter_id)
        volume = self.planner_service.get_volume(project_id, draft.volume_id)
        context_bundle = self._load_context_bundle(project_id, slug, draft, trigger)
        report_id = f"check_{uuid.uuid4().hex[:12]}"
        snapshot = self._build_source_snapshot(aggregate, volume, chapter, scene, draft)
        input_ctx = CheckInputContext(
            project_id=project_id,
            draft_id=draft_id,
            checker_run_id=report_id,
            draft_text=draft.content_md,
            draft_summary=draft.summary,
            story_bible=aggregate.story_bible,
            characters=aggregate.characters,
            world=aggregate.world,
            power_system=aggregate.power_system,
            volume=volume,
            chapter=chapter,
            scene=scene,
            context_bundle=context_bundle,
        )

        issues = []
        rule_summaries: list[CheckRuleSummary] = []
        overall_status = "clean"
        try:
            for evaluator in self.evaluators:
                family_issues = evaluator.evaluate(input_ctx)
                issues.extend(family_issues)
                rule_summaries.append(self._build_rule_summary(evaluator.rule_family, family_issues))
        except Exception:
            overall_status = "error"
            rule_summaries.append(
                CheckRuleSummary(
                    rule_family=getattr(evaluator, "rule_family", "checks"),
                    status="error",
                    issue_count=0,
                )
            )

        blocker_count = sum(1 for issue in issues if issue.severity == "blocker")
        warning_count = sum(1 for issue in issues if issue.severity == "warning")
        if overall_status != "error":
            overall_status = self._calculate_overall_status(blocker_count, warning_count)

        report = SceneDraftCheckReport(
            report_id=report_id,
            project_id=project_id,
            volume_id=draft.volume_id,
            chapter_id=draft.chapter_id,
            scene_id=draft.scene_id,
            draft_id=draft_id,
            trigger=trigger,
            created_at=utc_now(),
            source_versions=snapshot,
            overall_status=overall_status,
            blocker_count=blocker_count,
            warning_count=warning_count,
            issues=issues,
            rule_summaries=rule_summaries,
        )
        self._write_report(slug, draft, report)
        self._refresh_draft_check_summary(slug, draft, report)
        return report

    def get_latest_report(self, project_id: str, draft_id: str) -> SceneDraftCheckReport | None:
        slug = self._require_project(project_id)["slug"]
        draft = self._load_draft(project_id, draft_id)
        path = self._report_path(slug, draft)
        if not self.file_repository.exists(path):
            return None
        return SceneDraftCheckReport.model_validate(self.file_repository.read_json(path))

    def ensure_accept_allowed(self, project_id: str, draft_id: str) -> SceneDraftCheckReport:
        report = self.run_for_draft(project_id, draft_id, trigger="accept_preflight")
        if report.overall_status in {"blocked", "error"}:
            raise ConflictError("Draft checks blocked accept.")
        return report

    def _build_source_snapshot(self, aggregate, volume, chapter, scene, draft: SceneDraft) -> CheckSourceVersions:
        return CheckSourceVersions(
            story_bible_version=aggregate.story_bible.version,
            characters_version=aggregate.characters.version,
            world_version=aggregate.world.version,
            power_system_version=aggregate.power_system.version,
            volume_version=volume.version,
            chapter_version=chapter.version,
            scene_version=scene.version,
            draft_updated_at=draft.updated_at,
        )

    def _calculate_overall_status(self, blocker_count: int, warning_count: int) -> str:
        if blocker_count > 0:
            return "blocked"
        if warning_count > 0:
            return "warning"
        return "clean"

    def _build_rule_summary(self, rule_family: str, issues: list[Any]) -> CheckRuleSummary:
        blocker_count = sum(1 for issue in issues if issue.severity == "blocker")
        warning_count = sum(1 for issue in issues if issue.severity == "warning")
        return CheckRuleSummary(
            rule_family=rule_family,
            status=self._calculate_overall_status(blocker_count, warning_count),
            issue_count=len(issues),
        )

    def _load_context_bundle(self, project_id: str, slug: str, draft: SceneDraft, trigger: str) -> ContextBundle:
        if trigger == "generate_auto" and draft.context_bundle_path:
            path = self.paths.project_root(slug) / draft.context_bundle_path
            if self.file_repository.exists(path):
                try:
                    return ContextBundle.model_validate(self.file_repository.read_json(path))
                except Exception:
                    pass
        return self.context_bundle_service.build(project_id, draft.scene_id)

    def _refresh_draft_check_summary(self, slug: str, draft: SceneDraft, report: SceneDraftCheckReport) -> None:
        draft.latest_check_report_path = self.paths.relative_to_project(slug, self._report_path(slug, draft))
        draft.latest_check_run_id = report.report_id
        draft.last_check_status = report.overall_status
        draft.last_check_blocker_count = report.blocker_count
        draft.last_check_warning_count = report.warning_count
        self._write_draft(slug, draft)

    def _write_report(self, slug: str, draft: SceneDraft, report: SceneDraftCheckReport) -> None:
        self.file_repository.write_json(self._report_path(slug, draft), report.model_dump(mode="json"))

    def _report_path(self, slug: str, draft: SceneDraft):
        return self.paths.scene_draft_check_report_path(slug, draft.scene_id, draft.draft_id)

    def _write_draft(self, slug: str, draft: SceneDraft) -> None:
        if draft.draft_path:
            path = self.paths.project_root(slug) / draft.draft_path
        else:
            path = self.paths.scene_draft_path(slug, draft.scene_id, draft.draft_no)
            draft.draft_path = self.paths.relative_to_project(slug, path)
        self.file_repository.write_json(path, draft.model_dump(mode="json"))

    def _load_draft(self, project_id: str, draft_id: str) -> SceneDraft:
        slug = self._require_project(project_id)["slug"]
        for scene_dir in sorted(self.paths.scene_drafts_root(slug).glob("*")):
            if not scene_dir.is_dir():
                continue
            for draft_path in sorted(scene_dir.glob("draft-*.json")):
                draft = SceneDraft.model_validate(self.file_repository.read_json(draft_path))
                if draft.draft_id == draft_id:
                    return draft
        raise KeyError(draft_id)

    def _require_project(self, project_id: str) -> dict[str, Any]:
        project = self.sqlite_repository.get_project_record(project_id)
        if project is None:
            raise KeyError(project_id)
        return project
