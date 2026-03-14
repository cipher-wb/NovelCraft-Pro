from __future__ import annotations

from typing import Any

from backend.app.core.paths import AppPaths
from backend.app.domain.models.common import utc_now
from backend.app.domain.models.writing import (
    AcceptedSceneMemoryDocument,
    AcceptedSceneMemoryItem,
    BookAssembledDocument,
    BookSummaryMemoryDocument,
    ChapterAssembledDocument,
    ChapterSummariesMemoryDocument,
    ChapterSummaryMemoryItem,
    CharacterStateSummariesMemoryDocument,
    CharacterStateSummaryMemoryItem,
    RebuildReport,
    RebuildStepResult,
    SceneDraft,
    VolumeAssembledDocument,
    VolumeSummariesMemoryDocument,
    VolumeSummaryMemoryItem,
)
from backend.app.repositories.file_repository import FileRepository
from backend.app.repositories.sqlite_repository import SQLiteRepository
from backend.app.services.bible_service import BibleService
from backend.app.services.book_assembly_service import BookAssemblyService
from backend.app.services.book_checks_service import BookChecksService
from backend.app.services.book_continuity_checks_service import BookContinuityChecksService
from backend.app.services.chapter_assembly_service import ChapterAssemblyService
from backend.app.services.chapter_checks_service import ChapterChecksService
from backend.app.services.checks_service import ChecksService
from backend.app.services.exceptions import ConflictError
from backend.app.services.planner_service import PlannerService
from backend.app.services.project_artifact_inspector import ProjectArtifactInspector
from backend.app.services.volume_assembly_service import VolumeAssemblyService
from backend.app.services.volume_checks_service import VolumeChecksService


class RebuildService:
    DEFAULT_TARGETS = ["memory", "chapters", "volumes", "book", "checks"]

    def __init__(
        self,
        paths: AppPaths,
        file_repository: FileRepository,
        sqlite_repository: SQLiteRepository,
        bible_service: BibleService,
        planner_service: PlannerService,
        checks_service: ChecksService,
        chapter_checks_service: ChapterChecksService,
        volume_checks_service: VolumeChecksService,
        book_checks_service: BookChecksService,
        book_continuity_checks_service: BookContinuityChecksService,
        chapter_assembly_service: ChapterAssemblyService,
        volume_assembly_service: VolumeAssemblyService,
        book_assembly_service: BookAssemblyService,
    ) -> None:
        self.paths = paths
        self.file_repository = file_repository
        self.sqlite_repository = sqlite_repository
        self.bible_service = bible_service
        self.planner_service = planner_service
        self.checks_service = checks_service
        self.chapter_checks_service = chapter_checks_service
        self.volume_checks_service = volume_checks_service
        self.book_checks_service = book_checks_service
        self.book_continuity_checks_service = book_continuity_checks_service
        self.chapter_assembly_service = chapter_assembly_service
        self.volume_assembly_service = volume_assembly_service
        self.book_assembly_service = book_assembly_service
        self.inspector = ProjectArtifactInspector(paths, file_repository, planner_service)

    def rebuild(self, project_id: str, targets: list[str] | None = None) -> RebuildReport:
        project = self._require_project(project_id)
        slug = project["slug"]
        normalized_targets = self._normalize_targets(targets)
        started_at = utc_now()
        steps: list[RebuildStepResult] = []

        for target in normalized_targets:
            try:
                if target == "memory":
                    step = self._rebuild_memory(project_id, slug)
                elif target == "chapters":
                    step = self._rebuild_chapters(project_id, slug)
                elif target == "volumes":
                    step = self._rebuild_volumes(project_id, slug)
                elif target == "book":
                    step = self._rebuild_book(project_id, slug)
                else:
                    step = self._rebuild_checks(project_id, slug)
            except Exception as error:
                step = RebuildStepResult(
                    target=target,
                    status="failed",
                    details=[f"{target}: {error}"],
                )
            steps.append(step)

        return RebuildReport(
            project_id=project_id,
            started_at=started_at,
            finished_at=utc_now(),
            targets=normalized_targets,
            overall_status=self._overall_status(steps),
            steps=steps,
            warnings=[],
        )

    def _rebuild_memory(self, project_id: str, slug: str) -> RebuildStepResult:
        created_count = 0
        skipped_count = 0
        details: list[str] = []
        aggregate = self.bible_service.get_bible_aggregate(project_id)
        accepted_doc = AcceptedSceneMemoryDocument(
            project_id=project_id,
            updated_at=utc_now(),
            items=self._collect_current_accepted_scene_items(project_id, slug),
        )
        chapter_doc = self._build_chapter_summaries_document(project_id, slug, accepted_doc)
        character_doc = self._build_character_states_document(project_id, accepted_doc, aggregate.characters.items)
        volume_doc = self._build_volume_summaries_document(project_id, slug)
        book_doc = self._build_book_summary_document(project_id, slug)

        documents = [
            ("accepted_scenes.json", self.paths.accepted_scenes_memory_path(slug), accepted_doc),
            ("chapter_summaries.json", self.paths.chapter_summaries_memory_path(slug), chapter_doc),
            ("character_state_summaries.json", self.paths.character_state_summaries_memory_path(slug), character_doc),
            ("volume_summaries.json", self.paths.volume_summaries_memory_path(slug), volume_doc),
            ("book_summary.json", self.paths.book_summary_memory_path(slug), book_doc),
        ]
        for label, path, document in documents:
            if self.file_repository.exists(path):
                skipped_count += 1
                details.append(f"{label}: skipped existing document")
                continue
            self.file_repository.write_json(path, document.model_dump(mode="json"))
            created_count += 1
            details.append(f"{label}: created")

        return self._step_result(
            target="memory",
            created_count=created_count,
            skipped_count=skipped_count,
            details=details,
        )

    def _normalize_targets(self, targets: list[str] | None) -> list[str]:
        if not targets:
            return list(self.DEFAULT_TARGETS)
        normalized = [target for target in self.DEFAULT_TARGETS if target in targets]
        if sorted(set(targets)) != sorted(set(normalized)):
            raise ValueError("Unsupported rebuild targets.")
        return normalized

    def _overall_status(self, steps: list[RebuildStepResult]) -> str:
        if steps and all(step.status == "failed" for step in steps):
            return "failed"
        if any(step.status in {"failed", "partial"} for step in steps):
            return "partial"
        return "success"

    def _step_result(
        self,
        *,
        target: str,
        created_count: int = 0,
        updated_count: int = 0,
        skipped_count: int = 0,
        stale_count: int = 0,
        details: list[str] | None = None,
        failures: int = 0,
    ) -> RebuildStepResult:
        details = details or []
        if failures and (created_count or updated_count or skipped_count or stale_count):
            status = "partial"
        elif failures:
            status = "failed"
        elif not (created_count or updated_count or stale_count) and skipped_count:
            status = "skipped"
        else:
            status = "success"
        return RebuildStepResult(
            target=target,
            status=status,
            created_count=created_count,
            updated_count=updated_count,
            skipped_count=skipped_count,
            stale_count=stale_count,
            details=details,
        )

    def _require_project(self, project_id: str) -> dict[str, Any]:
        project = self.sqlite_repository.get_project_record(project_id)
        if project is None:
            raise KeyError(project_id)
        return project

    def _collect_current_accepted_scene_items(self, project_id: str, slug: str) -> list[AcceptedSceneMemoryItem]:
        items: list[AcceptedSceneMemoryItem] = []
        for volume in self.planner_service.list_volumes(project_id):
            for chapter in self.planner_service.list_chapters(project_id, volume.volume_id):
                for scene in self.planner_service.list_scenes(project_id, chapter.chapter_id):
                    accepted = self.inspector.accepted_drafts_for_scene(slug, scene.scene_id)
                    if len(accepted) != 1:
                        continue
                    draft = accepted[0]
                    items.append(
                        AcceptedSceneMemoryItem(
                            memory_id=f"mem_{draft.draft_id}",
                            scene_id=scene.scene_id,
                            chapter_id=scene.chapter_id,
                            volume_id=scene.volume_id,
                            draft_id=draft.draft_id,
                            chapter_no=scene.chapter_no,
                            scene_no=scene.scene_no,
                            volume_no=volume.volume_no,
                            chapter_title=chapter.title,
                            scene_title=scene.title,
                            scene_type=scene.scene_type,
                            summary=draft.summary or self._fallback_summary(draft.content_md, scene.title),
                            summary_source="draft_summary" if draft.summary else "heuristic_fallback",
                            scene_goal=scene.goal,
                            scene_outcome=scene.outcome,
                            character_ids=scene.character_ids,
                            faction_ids=chapter.faction_ids,
                            location_id=scene.location_id,
                            time_anchor=scene.time_anchor,
                            accepted_at=draft.accepted_at or draft.updated_at,
                            source_scene_version=draft.source_scene_version,
                        )
                    )
        return sorted(items, key=lambda value: (value.chapter_no, value.scene_no, value.draft_id))

    def _build_chapter_summaries_document(
        self,
        project_id: str,
        slug: str,
        accepted_doc: AcceptedSceneMemoryDocument,
    ) -> ChapterSummariesMemoryDocument:
        items: list[ChapterSummaryMemoryItem] = []
        accepted_by_chapter: dict[str, list[AcceptedSceneMemoryItem]] = {}
        for item in accepted_doc.items:
            accepted_by_chapter.setdefault(item.chapter_id, []).append(item)

        for volume in self.planner_service.list_volumes(project_id):
            for chapter in self.planner_service.list_chapters(project_id, volume.volume_id):
                chapter_path = self.paths.chapter_assembled_path(slug, chapter.chapter_id)
                if self.file_repository.exists(chapter_path):
                    artifact = ChapterAssembledDocument.model_validate(self.file_repository.read_json(chapter_path))
                    if artifact.status == "finalized":
                        last_scene = artifact.scene_order[-1] if artifact.scene_order else None
                        items.append(
                            ChapterSummaryMemoryItem(
                                chapter_id=artifact.chapter_id,
                                volume_id=artifact.volume_id,
                                chapter_no=artifact.chapter_no,
                                chapter_title=chapter.title,
                                accepted_scene_ids=[entry.scene_id for entry in artifact.scene_order],
                                accepted_scene_count=len(artifact.scene_order),
                                summary=artifact.summary,
                                hook=artifact.hook,
                                summary_source="finalized_chapter",
                                key_turns=[artifact.hook] if artifact.hook else [],
                                last_scene_id=last_scene.scene_id if last_scene else None,
                                last_scene_no=last_scene.scene_no if last_scene else None,
                                updated_from_draft_id=last_scene.accepted_draft_id if last_scene else None,
                                updated_at=utc_now(),
                            )
                        )
                        continue

                chapter_items = sorted(accepted_by_chapter.get(chapter.chapter_id, []), key=lambda value: (value.scene_no, value.draft_id))
                if not chapter_items:
                    continue
                items.append(
                    ChapterSummaryMemoryItem(
                        chapter_id=chapter.chapter_id,
                        volume_id=chapter.volume_id,
                        chapter_no=chapter.chapter_no,
                        chapter_title=chapter.title,
                        accepted_scene_ids=[item.scene_id for item in chapter_items],
                        accepted_scene_count=len(chapter_items),
                        summary=" | ".join(f"{item.scene_title}：{item.summary}" for item in chapter_items[:3]),
                        hook="",
                        summary_source="accepted_scene_rollup",
                        key_turns=[f"{item.scene_title}：{item.scene_goal} -> {item.scene_outcome}" for item in chapter_items[:3]],
                        last_scene_id=chapter_items[-1].scene_id,
                        last_scene_no=chapter_items[-1].scene_no,
                        updated_from_draft_id=chapter_items[-1].draft_id,
                        updated_at=utc_now(),
                    )
                )
        return ChapterSummariesMemoryDocument(
            project_id=project_id,
            updated_at=utc_now(),
            items=sorted(items, key=lambda value: (value.chapter_no, value.chapter_id)),
        )

    def _build_character_states_document(
        self,
        project_id: str,
        accepted_doc: AcceptedSceneMemoryDocument,
        characters: list[Any],
    ) -> CharacterStateSummariesMemoryDocument:
        character_names = {item.character_id: item.name for item in characters}
        latest_by_character: dict[str, CharacterStateSummaryMemoryItem] = {}
        for item in accepted_doc.items:
            unique_related: list[str] = []
            seen_related: set[str] = set()
            for related in item.character_ids:
                if related in seen_related:
                    continue
                seen_related.add(related)
                unique_related.append(related)
            for character_id in unique_related:
                latest_by_character[character_id] = CharacterStateSummaryMemoryItem(
                    character_id=character_id,
                    character_name=character_names.get(character_id, character_id),
                    last_scene_id=item.scene_id,
                    last_chapter_id=item.chapter_id,
                    last_volume_id=item.volume_id,
                    last_chapter_no=item.chapter_no,
                    last_scene_no=item.scene_no,
                    latest_location_id=item.location_id,
                    latest_time_anchor=item.time_anchor,
                    latest_scene_summary=item.summary,
                    last_scene_goal=item.scene_goal,
                    last_scene_outcome=item.scene_outcome,
                    related_character_ids=[related for related in unique_related if related != character_id],
                    source_draft_id=item.draft_id,
                    updated_at=utc_now(),
                )
        return CharacterStateSummariesMemoryDocument(
            project_id=project_id,
            updated_at=utc_now(),
            items=sorted(latest_by_character.values(), key=lambda value: value.character_id),
        )

    def _build_volume_summaries_document(self, project_id: str, slug: str) -> VolumeSummariesMemoryDocument:
        items: list[VolumeSummaryMemoryItem] = []
        for volume in self.planner_service.list_volumes(project_id):
            path = self.paths.volume_assembled_path(slug, volume.volume_id)
            if not self.file_repository.exists(path):
                continue
            artifact = VolumeAssembledDocument.model_validate(self.file_repository.read_json(path))
            if artifact.status != "finalized":
                continue
            items.append(
                VolumeSummaryMemoryItem(
                    volume_id=artifact.volume_id,
                    volume_no=artifact.volume_no,
                    title=volume.title,
                    summary=artifact.summary,
                    hook=artifact.hook,
                    planned_chapter_count=artifact.progress_stats.planned_chapter_count,
                    finalized_chapter_count=artifact.progress_stats.finalized_chapter_count,
                    finalized_chapter_ids=[entry.chapter_id for entry in artifact.chapter_order],
                    updated_at=utc_now(),
                )
            )
        return VolumeSummariesMemoryDocument(
            project_id=project_id,
            updated_at=utc_now(),
            items=sorted(items, key=lambda value: (value.volume_no, value.volume_id)),
        )

    def _build_book_summary_document(self, project_id: str, slug: str) -> BookSummaryMemoryDocument:
        path = self.paths.book_assembled_path(slug)
        if self.file_repository.exists(path):
            artifact = BookAssembledDocument.model_validate(self.file_repository.read_json(path))
            if artifact.status == "finalized":
                return BookSummaryMemoryDocument(
                    project_id=project_id,
                    updated_at=utc_now(),
                    summary=artifact.summary,
                    hook=artifact.hook,
                    planned_volume_count=artifact.progress_stats.planned_volume_count,
                    finalized_volume_count=artifact.progress_stats.finalized_volume_count,
                    finalized_volume_ids=[item.volume_id for item in artifact.volume_order],
                )
        return BookSummaryMemoryDocument(project_id=project_id, updated_at=utc_now())

    def _fallback_summary(self, content_md: str, title: str) -> str:
        text = " ".join(part.strip() for part in content_md.splitlines() if part.strip())
        return text[:120] if text else title

    def _rebuild_chapters(self, project_id: str, slug: str) -> RebuildStepResult:
        created_count = 0
        updated_count = 0
        skipped_count = 0
        stale_count = 0
        details: list[str] = []
        failures = 0
        for volume in self.planner_service.list_volumes(project_id):
            for chapter in self.planner_service.list_chapters(project_id, volume.volume_id):
                path = self.paths.chapter_assembled_path(slug, chapter.chapter_id)
                if not self.file_repository.exists(path):
                    try:
                        self.chapter_assembly_service.assemble(project_id, chapter.chapter_id)
                        created_count += 1
                        details.append(f"{chapter.chapter_id}: assembled missing artifact")
                    except ConflictError as error:
                        skipped_count += 1
                        details.append(f"{chapter.chapter_id}: skipped ({error})")
                    except Exception as error:
                        failures += 1
                        details.append(f"{chapter.chapter_id}: failed ({error})")
                    continue
                try:
                    artifact = ChapterAssembledDocument.model_validate(self.file_repository.read_json(path))
                    if artifact.status != "stale" and self.inspector.is_chapter_artifact_stale(project_id, slug, artifact):
                        artifact.status = "stale"
                        artifact.updated_at = utc_now()
                        self.file_repository.write_json(path, artifact.model_dump(mode="json"))
                        updated_count += 1
                        stale_count += 1
                        details.append(f"{chapter.chapter_id}: downgraded to stale")
                    else:
                        skipped_count += 1
                        details.append(f"{chapter.chapter_id}: skipped existing artifact")
                except Exception as error:
                    failures += 1
                    details.append(f"{chapter.chapter_id}: failed ({error})")
        return self._step_result(
            target="chapters",
            created_count=created_count,
            updated_count=updated_count,
            skipped_count=skipped_count,
            stale_count=stale_count,
            details=details,
            failures=failures,
        )

    def _rebuild_volumes(self, project_id: str, slug: str) -> RebuildStepResult:
        created_count = 0
        updated_count = 0
        skipped_count = 0
        stale_count = 0
        details: list[str] = []
        failures = 0
        for volume in self.planner_service.list_volumes(project_id):
            path = self.paths.volume_assembled_path(slug, volume.volume_id)
            if not self.file_repository.exists(path):
                try:
                    self.volume_assembly_service.assemble(project_id, volume.volume_id)
                    created_count += 1
                    details.append(f"{volume.volume_id}: assembled missing artifact")
                except ConflictError as error:
                    skipped_count += 1
                    details.append(f"{volume.volume_id}: skipped ({error})")
                except Exception as error:
                    failures += 1
                    details.append(f"{volume.volume_id}: failed ({error})")
                continue
            try:
                artifact = VolumeAssembledDocument.model_validate(self.file_repository.read_json(path))
                if artifact.status != "stale" and self.inspector.is_volume_artifact_stale(project_id, slug, artifact):
                    artifact.status = "stale"
                    artifact.updated_at = utc_now()
                    self.file_repository.write_json(path, artifact.model_dump(mode="json"))
                    updated_count += 1
                    stale_count += 1
                    details.append(f"{volume.volume_id}: downgraded to stale")
                else:
                    skipped_count += 1
                    details.append(f"{volume.volume_id}: skipped existing artifact")
            except Exception as error:
                failures += 1
                details.append(f"{volume.volume_id}: failed ({error})")
        return self._step_result(
            target="volumes",
            created_count=created_count,
            updated_count=updated_count,
            skipped_count=skipped_count,
            stale_count=stale_count,
            details=details,
            failures=failures,
        )

    def _rebuild_book(self, project_id: str, slug: str) -> RebuildStepResult:
        created_count = 0
        updated_count = 0
        skipped_count = 0
        stale_count = 0
        details: list[str] = []
        path = self.paths.book_assembled_path(slug)
        if not self.file_repository.exists(path):
            try:
                self.book_assembly_service.assemble(project_id)
                created_count = 1
                details.append("book: assembled missing artifact")
            except ConflictError as error:
                skipped_count = 1
                details.append(f"book: skipped ({error})")
            except Exception as error:
                return self._step_result(target="book", details=[f"book: failed ({error})"], failures=1)
            return self._step_result(
                target="book",
                created_count=created_count,
                skipped_count=skipped_count,
                details=details,
            )

        try:
            artifact = BookAssembledDocument.model_validate(self.file_repository.read_json(path))
            if artifact.status != "stale" and self.inspector.is_book_artifact_stale(project_id, slug, artifact):
                artifact.status = "stale"
                artifact.updated_at = utc_now()
                self.file_repository.write_json(path, artifact.model_dump(mode="json"))
                updated_count = 1
                stale_count = 1
                details.append("book: downgraded to stale")
            else:
                skipped_count = 1
                details.append("book: skipped existing artifact")
        except Exception as error:
            return self._step_result(target="book", details=[f"book: failed ({error})"], failures=1)

        return self._step_result(
            target="book",
            updated_count=updated_count,
            skipped_count=skipped_count,
            stale_count=stale_count,
            details=details,
        )

    def _rebuild_checks(self, project_id: str, slug: str) -> RebuildStepResult:
        created_count = 0
        skipped_count = 0
        details: list[str] = []
        failures = 0

        for draft in self._current_unique_accepted_drafts(slug):
            report_path = self._scene_report_path(slug, draft)
            if self.file_repository.exists(report_path):
                skipped_count += 1
                details.append(f"{draft.draft_id}: skipped existing draft report")
                continue
            try:
                self.checks_service.run_for_draft(project_id, draft.draft_id, trigger="rebuild_sync")
                created_count += 1
                details.append(f"{draft.draft_id}: rebuilt draft report")
            except Exception as error:
                failures += 1
                details.append(f"{draft.draft_id}: failed ({error})")

        for volume in self.planner_service.list_volumes(project_id):
            for chapter in self.planner_service.list_chapters(project_id, volume.volume_id):
                chapter_path = self.paths.chapter_assembled_path(slug, chapter.chapter_id)
                if not self.file_repository.exists(chapter_path):
                    continue
                try:
                    assembled = ChapterAssembledDocument.model_validate(self.file_repository.read_json(chapter_path))
                    report_path = self._chapter_report_path(slug, assembled)
                    if self.file_repository.exists(report_path):
                        skipped_count += 1
                        details.append(f"{chapter.chapter_id}: skipped existing chapter report")
                    else:
                        self.chapter_checks_service.run_for_chapter(project_id, assembled, trigger="rebuild_sync")
                        created_count += 1
                        details.append(f"{chapter.chapter_id}: rebuilt chapter report")
                except Exception as error:
                    failures += 1
                    details.append(f"{chapter.chapter_id}: failed ({error})")

            volume_path = self.paths.volume_assembled_path(slug, volume.volume_id)
            if not self.file_repository.exists(volume_path):
                continue
            try:
                assembled = VolumeAssembledDocument.model_validate(self.file_repository.read_json(volume_path))
                report_path = self._volume_report_path(slug, assembled)
                if self.file_repository.exists(report_path):
                    skipped_count += 1
                    details.append(f"{volume.volume_id}: skipped existing volume report")
                else:
                    self.volume_checks_service.run_for_volume(project_id, assembled, trigger="rebuild_sync")
                    created_count += 1
                    details.append(f"{volume.volume_id}: rebuilt volume report")
            except Exception as error:
                failures += 1
                details.append(f"{volume.volume_id}: failed ({error})")

        book_path = self.paths.book_assembled_path(slug)
        if self.file_repository.exists(book_path):
            try:
                assembled = BookAssembledDocument.model_validate(self.file_repository.read_json(book_path))
                book_report_path = self._book_report_path(slug, assembled)
                if self.file_repository.exists(book_report_path):
                    skipped_count += 1
                    details.append("book: skipped existing book report")
                else:
                    self.book_checks_service.run_for_book(project_id, assembled, trigger="rebuild_sync")
                    created_count += 1
                    details.append("book: rebuilt book report")

                continuity_path = self._book_continuity_report_path(slug, assembled)
                if self.file_repository.exists(continuity_path):
                    skipped_count += 1
                    details.append("book: skipped existing continuity report")
                else:
                    self.book_continuity_checks_service.run_for_book(project_id, "rebuild_sync")
                    created_count += 1
                    details.append("book: rebuilt continuity report")
            except Exception as error:
                failures += 1
                details.append(f"book: failed ({error})")

        return self._step_result(
            target="checks",
            created_count=created_count,
            skipped_count=skipped_count,
            details=details,
            failures=failures,
        )

    def _current_unique_accepted_drafts(self, slug: str) -> list[SceneDraft]:
        accepted: list[SceneDraft] = []
        for scene_dir in sorted(self.paths.scene_drafts_root(slug).glob("*")):
            if not scene_dir.is_dir():
                continue
            scene_accepted = self.inspector.accepted_drafts_for_scene(slug, scene_dir.name)
            if len(scene_accepted) == 1:
                accepted.append(scene_accepted[0])
        return sorted(accepted, key=lambda value: (value.chapter_no, value.scene_no, value.draft_no))

    def _scene_report_path(self, slug: str, draft: SceneDraft):
        if draft.latest_check_report_path:
            return self.paths.project_root(slug) / draft.latest_check_report_path
        return self.paths.scene_draft_check_report_path(slug, draft.scene_id, draft.draft_id)

    def _chapter_report_path(self, slug: str, assembled: ChapterAssembledDocument):
        if assembled.latest_check_report_path:
            return self.paths.project_root(slug) / assembled.latest_check_report_path
        return self.paths.chapter_check_latest_path(slug, assembled.chapter_id)

    def _volume_report_path(self, slug: str, assembled: VolumeAssembledDocument):
        if assembled.latest_check_report_path:
            return self.paths.project_root(slug) / assembled.latest_check_report_path
        return self.paths.volume_check_latest_path(slug, assembled.volume_id)

    def _book_report_path(self, slug: str, assembled: BookAssembledDocument):
        if assembled.latest_check_report_path:
            return self.paths.project_root(slug) / assembled.latest_check_report_path
        return self.paths.book_check_latest_path(slug)

    def _book_continuity_report_path(self, slug: str, assembled: BookAssembledDocument):
        if assembled.latest_continuity_check_report_path:
            return self.paths.project_root(slug) / assembled.latest_continuity_check_report_path
        return self.paths.book_continuity_check_latest_path(slug)
