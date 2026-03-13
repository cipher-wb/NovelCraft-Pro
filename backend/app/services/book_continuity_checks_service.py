from __future__ import annotations

import uuid

from backend.app.core.paths import AppPaths
from backend.app.domain.models.common import utc_now
from backend.app.domain.models.issues import (
    BookContinuityCheckReport,
    BookContinuityCheckSourceVersions,
    CheckRuleSummary,
)
from backend.app.domain.models.planning import MasterOutlineDocument
from backend.app.domain.models.project import (
    CharacterDocument,
    PowerSystemDocument,
    StoryBible,
    WorldDocument,
)
from backend.app.domain.models.writing import (
    AcceptedSceneMemoryDocument,
    BookAssembledDocument,
    BookSummaryMemoryDocument,
    ChapterSummariesMemoryDocument,
    CharacterStateSummariesMemoryDocument,
    VolumeAssembledDocument,
    VolumeSummariesMemoryDocument,
)
from backend.app.repositories.file_repository import FileRepository
from backend.app.repositories.sqlite_repository import SQLiteRepository
from backend.app.services.bible_service import BibleService
from backend.app.services.book_continuity_rule_evaluators import (
    BookContinuityCheckInput,
    CrossVolumeProgressionEvaluator,
    FinalizedVolumeEntry,
    LongArcCharacterEvaluator,
    MainGoalProgressionEvaluator,
    ThreadDriftEvaluator,
    WorldPowerCrossVolumeEvaluator,
)
from backend.app.services.planner_service import PlannerService


class BookContinuityChecksService:
    def __init__(
        self,
        paths: AppPaths,
        file_repository: FileRepository,
        sqlite_repository: SQLiteRepository,
        bible_service: BibleService,
        planner_service: PlannerService,
    ) -> None:
        self.paths = paths
        self.file_repository = file_repository
        self.sqlite_repository = sqlite_repository
        self.bible_service = bible_service
        self.planner_service = planner_service
        self.evaluators = [
            LongArcCharacterEvaluator(),
            WorldPowerCrossVolumeEvaluator(),
            MainGoalProgressionEvaluator(),
            ThreadDriftEvaluator(),
            CrossVolumeProgressionEvaluator(),
        ]

    def get_latest_report(self, project_id: str) -> BookContinuityCheckReport | None:
        slug = self._require_project(project_id)["slug"]
        path = self.paths.book_continuity_check_latest_path(slug)
        if not self.file_repository.exists(path):
            return None
        return BookContinuityCheckReport.model_validate(self.file_repository.read_json(path))

    def run_for_book(self, project_id: str, trigger: str) -> BookContinuityCheckReport:
        project = self._require_project(project_id)
        slug = project["slug"]
        assembled = self._read_book_assembled(slug)
        input_context = self._build_input(project_id, slug, assembled)
        try:
            issues = []
            for evaluator in self.evaluators:
                issues.extend(evaluator.evaluate(input_context))
            report = self._build_report(input_context, trigger, issues)
        except Exception:
            report = BookContinuityCheckReport(
                report_id=f"book_continuity_{uuid.uuid4().hex[:12]}",
                project_id=project_id,
                trigger=trigger,
                created_at=utc_now(),
                source_versions=self._source_versions(input_context),
                overall_status="error",
                blocker_count=0,
                warning_count=0,
                issues=[],
                rule_summaries=[CheckRuleSummary(rule_family="book_continuity", status="error", issue_count=0)],
            )
        self._write_report(slug, report)
        assembled.latest_continuity_check_report_path = self.paths.relative_to_project(slug, self.paths.book_continuity_check_latest_path(slug))
        assembled.last_continuity_check_status = report.overall_status
        assembled.last_continuity_check_blocker_count = report.blocker_count
        assembled.last_continuity_check_warning_count = report.warning_count
        self._write_book_assembled(slug, assembled)
        return report

    def ensure_finalize_allowed(self, project_id: str) -> BookContinuityCheckReport:
        return self.run_for_book(project_id, "finalize_preflight")

    def _build_input(self, project_id: str, slug: str, assembled: BookAssembledDocument) -> BookContinuityCheckInput:
        aggregate = self.bible_service.get_bible_aggregate(project_id)
        master_outline = self.planner_service.get_master_outline(project_id)
        planned_volumes = self.planner_service.list_volumes(project_id)
        volume_plans_by_id = {volume.volume_id: volume for volume in planned_volumes}
        finalized_volumes: list[FinalizedVolumeEntry] = []
        for item in assembled.volume_order:
            volume_plan = volume_plans_by_id.get(item.volume_id)
            if volume_plan is None:
                raise ValueError(f"Missing canonical volume {item.volume_id}.")
            path = self.paths.volume_assembled_path(slug, item.volume_id)
            if not self.file_repository.exists(path):
                raise ValueError(f"Missing finalized volume artifact for {item.volume_id}.")
            artifact = VolumeAssembledDocument.model_validate(self.file_repository.read_json(path))
            if artifact.status != "finalized":
                raise ValueError(f"Volume artifact {item.volume_id} is not finalized.")
            finalized_volumes.append(FinalizedVolumeEntry(volume=volume_plan, artifact=artifact))

        checker_run_id = f"book_continuity_{uuid.uuid4().hex[:12]}"
        detected_at = utc_now()
        return BookContinuityCheckInput(
            project_id=project_id,
            checker_run_id=checker_run_id,
            detected_at=detected_at,
            story_bible=aggregate.story_bible,
            characters=aggregate.characters,
            world=aggregate.world,
            power_system=aggregate.power_system,
            planned_volumes=planned_volumes,
            finalized_volumes=finalized_volumes,
            book_assembled=assembled,
            accepted_scenes=self._safe_memory_doc(
                self.paths.accepted_scenes_memory_path(slug),
                AcceptedSceneMemoryDocument,
                project_id,
            ),
            chapter_summaries=self._safe_memory_doc(
                self.paths.chapter_summaries_memory_path(slug),
                ChapterSummariesMemoryDocument,
                project_id,
            ),
            character_state_summaries=self._safe_memory_doc(
                self.paths.character_state_summaries_memory_path(slug),
                CharacterStateSummariesMemoryDocument,
                project_id,
            ),
            volume_summaries=self._safe_memory_doc(
                self.paths.volume_summaries_memory_path(slug),
                VolumeSummariesMemoryDocument,
                project_id,
            ),
            book_summary=self._safe_memory_doc(
                self.paths.book_summary_memory_path(slug),
                BookSummaryMemoryDocument,
                project_id,
            ),
        )

    def _safe_memory_doc(self, path, model_cls, project_id: str):
        if not self.file_repository.exists(path):
            return model_cls(project_id=project_id, updated_at=utc_now(), version=0)
        return model_cls.model_validate(self.file_repository.read_json(path))

    def _build_report(
        self,
        input_context: BookContinuityCheckInput,
        trigger: str,
        issues,
    ) -> BookContinuityCheckReport:
        blocker_count = sum(1 for issue in issues if issue.severity == "blocker")
        warning_count = sum(1 for issue in issues if issue.severity == "warning")
        if blocker_count > 0:
            overall_status = "blocked"
        elif warning_count > 0:
            overall_status = "warning"
        else:
            overall_status = "clean"
        return BookContinuityCheckReport(
            report_id=f"book_continuity_{uuid.uuid4().hex[:12]}",
            project_id=input_context.project_id,
            trigger=trigger,
            created_at=utc_now(),
            source_versions=self._source_versions(input_context),
            overall_status=overall_status,
            blocker_count=blocker_count,
            warning_count=warning_count,
            issues=issues,
            rule_summaries=[CheckRuleSummary(rule_family="book_continuity", status=overall_status, issue_count=len(issues))],
        )

    def _source_versions(self, input_context: BookContinuityCheckInput) -> BookContinuityCheckSourceVersions:
        return BookContinuityCheckSourceVersions(
            story_bible_version=input_context.story_bible.version,
            characters_version=input_context.characters.version,
            world_version=input_context.world.version,
            power_system_version=input_context.power_system.version,
            master_outline_version=input_context.book_assembled.source_versions.master_outline_version,
            planned_volume_versions=dict(input_context.book_assembled.source_versions.planned_volume_versions),
            finalized_volume_versions=dict(input_context.book_assembled.source_versions.finalized_volume_versions),
            book_assembled_version=input_context.book_assembled.version,
            accepted_scenes_version=input_context.accepted_scenes.version,
            chapter_summaries_version=input_context.chapter_summaries.version,
            character_state_summaries_version=input_context.character_state_summaries.version,
            volume_summaries_version=input_context.volume_summaries.version,
            book_summary_version=input_context.book_summary.version,
        )

    def _read_book_assembled(self, slug: str) -> BookAssembledDocument:
        path = self.paths.book_assembled_path(slug)
        if not self.file_repository.exists(path):
            raise KeyError(slug)
        return BookAssembledDocument.model_validate(self.file_repository.read_json(path))

    def _write_book_assembled(self, slug: str, assembled: BookAssembledDocument) -> None:
        self.file_repository.write_json(self.paths.book_assembled_path(slug), assembled.model_dump(mode="json"))

    def _write_report(self, slug: str, report: BookContinuityCheckReport) -> None:
        self.file_repository.write_json(self.paths.book_continuity_check_latest_path(slug), report.model_dump(mode="json"))

    def _require_project(self, project_id: str) -> dict:
        project = self.sqlite_repository.get_project_record(project_id)
        if project is None:
            raise KeyError(project_id)
        return project
