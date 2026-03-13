from __future__ import annotations

import json
import uuid
from pathlib import Path

from backend.app.core.paths import AppPaths
from backend.app.domain.models.common import DraftStatus, utc_now
from backend.app.domain.models.issues import ConsistencyIssue, SceneDraftCheckReport
from backend.app.domain.models.writing import ContextBundle, RepairMetadata, SceneDraft, SceneDraftManifest, SceneDraftManifestItem
from backend.app.infra.llm_gateway import GenerateRequest, MockLLMGateway
from backend.app.repositories.file_repository import FileRepository
from backend.app.repositories.sqlite_repository import SQLiteRepository
from backend.app.services.checks_service import ChecksService
from backend.app.services.context_bundle_service import ContextBundleService
from backend.app.services.exceptions import ConflictError
from backend.app.services.planner_service import PlannerService
from backend.app.services.scene_draft_service import SceneDraftService
from backend.app.services.style_service import StyleService


class RepairService:
    def __init__(
        self,
        paths: AppPaths,
        file_repository: FileRepository,
        sqlite_repository: SQLiteRepository,
        planner_service: PlannerService,
        scene_draft_service: SceneDraftService,
        context_bundle_service: ContextBundleService,
        checks_service: ChecksService,
        style_service: StyleService | None,
        llm_gateway,
    ) -> None:
        self.paths = paths
        self.file_repository = file_repository
        self.sqlite_repository = sqlite_repository
        self.planner_service = planner_service
        self.scene_draft_service = scene_draft_service
        self.context_bundle_service = context_bundle_service
        self.checks_service = checks_service
        self.style_service = style_service
        self.llm_gateway = llm_gateway

    def repair_draft(self, project_id: str, draft_id: str, issue_ids: list[str] | None = None) -> SceneDraft:
        project = self._require_project(project_id)
        slug = project["slug"]
        source = self.scene_draft_service.get_draft(project_id, draft_id)
        if source.status != DraftStatus.draft.value:
            raise ConflictError("Only draft status can be repaired.")

        scene = self.planner_service.get_scene(project_id, source.scene_id)
        chapter = self.planner_service.get_chapter(project_id, source.chapter_id)
        volume = self.planner_service.get_volume(project_id, source.volume_id)
        report = self._get_latest_usable_report(project_id, source)
        source = self.scene_draft_service.get_draft(project_id, draft_id)
        if report.overall_status == "clean":
            raise ConflictError("Clean drafts do not need repair.")
        if report.overall_status == "error":
            raise ConflictError("Draft checks are in error state; repair is not allowed.")

        selected_issues = self._select_target_issues(report, issue_ids)
        if not selected_issues:
            raise ConflictError("No open issues available for repair.")

        manifest = self.scene_draft_service.get_scene_manifest(project_id, source.scene_id)
        draft_no = manifest.last_draft_no + 1
        bundle = self._load_fresh_bundle(project_id, source)
        content_md, summary = self._generate_repaired_content(source, bundle, scene, selected_issues)
        now = utc_now()
        repaired_draft_id = f"draft_{uuid.uuid4().hex[:12]}"
        bundle_path = self.paths.scene_context_bundle_path(slug, source.scene_id, draft_no)
        draft_path = self.paths.scene_draft_path(slug, source.scene_id, draft_no)

        blocker_issue_ids = [issue.issue_id for issue in selected_issues if issue.severity == "blocker"]
        warning_issue_ids = [issue.issue_id for issue in selected_issues if issue.severity == "warning"]
        repaired = SceneDraft(
            draft_id=repaired_draft_id,
            project_id=project_id,
            volume_id=source.volume_id,
            chapter_id=source.chapter_id,
            scene_id=source.scene_id,
            chapter_no=source.chapter_no,
            scene_no=source.scene_no,
            draft_no=draft_no,
            operation="repair",
            candidate_mode=source.candidate_mode,
            status=DraftStatus.draft.value,
            content_md=content_md,
            summary=summary,
            repair_metadata=RepairMetadata(
                source_draft_id=source.draft_id,
                source_check_run_id=report.report_id,
                source_check_report_path=source.latest_check_report_path or self.paths.relative_to_project(slug, self.paths.scene_draft_check_report_path(slug, source.scene_id, source.draft_id)),
                selected_issue_ids=[issue.issue_id for issue in selected_issues],
                selected_blocker_issue_ids=blocker_issue_ids,
                selected_warning_issue_ids=warning_issue_ids,
                repair_strategy_version="targeted_repair_v1",
                repair_summary=f"Repair {len(blocker_issue_ids)} blockers and {len(warning_issue_ids)} warnings from {source.draft_id}.",
            ),
            context_bundle_id=bundle.context_bundle_id,
            context_bundle_path=self.paths.relative_to_project(slug, bundle_path),
            draft_path=self.paths.relative_to_project(slug, draft_path),
            latest_check_report_path=None,
            latest_check_run_id=None,
            last_check_status=None,
            last_check_blocker_count=0,
            last_check_warning_count=0,
            model_name=self._model_name(),
            tokens_in=0,
            tokens_out=0,
            source_scene_version=scene.version,
            source_chapter_version=chapter.version,
            source_volume_version=volume.version,
            created_at=now,
            updated_at=now,
            accepted_at=None,
            rejected_at=None,
            supersedes_draft_id=source.draft_id,
            memory_stub_record_id=None,
        )

        source_original = source.model_dump(mode="json")
        created_paths: list[Path] = []
        source_written = False
        try:
            self.file_repository.write_json(bundle_path, bundle.model_dump(mode="json"))
            created_paths.append(bundle_path)
            self.file_repository.write_json(draft_path, repaired.model_dump(mode="json"))
            created_paths.append(draft_path)
            self.checks_service.run_for_draft(project_id, repaired.draft_id, trigger="repair_auto")
            repaired = self.scene_draft_service.get_draft(project_id, repaired.draft_id)
            if repaired.latest_check_report_path:
                report_path = self.paths.project_root(slug) / repaired.latest_check_report_path
                if self.file_repository.exists(report_path):
                    created_paths.append(report_path)

            source.status = DraftStatus.superseded.value
            source.updated_at = utc_now()
            self._write_draft(slug, source)
            source_written = True

            refreshed_manifest = self.scene_draft_service.get_scene_manifest(project_id, source.scene_id)
            manifest_items = [
                self._manifest_item_from_draft(self.scene_draft_service.get_draft(project_id, item.draft_id))
                for item in refreshed_manifest.items
                if item.draft_id != repaired.draft_id
            ]
            manifest_items.append(self._manifest_item_from_draft(repaired))
            refreshed_manifest.items = sorted(manifest_items, key=lambda value: value.draft_no)
            refreshed_manifest.latest_draft_id = repaired.draft_id
            refreshed_manifest.last_draft_no = draft_no
            refreshed_manifest.version += 1
            refreshed_manifest.updated_at = utc_now()
            self._write_manifest(slug, source.scene_id, refreshed_manifest)
            return self.scene_draft_service.get_draft(project_id, repaired.draft_id)
        except Exception as error:
            if source_written:
                try:
                    self._write_draft(slug, SceneDraft.model_validate(source_original))
                except Exception:
                    pass
            self._cleanup_created_paths(created_paths)
            raise ConflictError(f"Repair failed: {error}") from error

    def _get_latest_usable_report(self, project_id: str, source: SceneDraft) -> SceneDraftCheckReport:
        aggregate = self.scene_draft_service.bible_service.get_bible_aggregate(project_id)
        scene = self.planner_service.get_scene(project_id, source.scene_id)
        chapter = self.planner_service.get_chapter(project_id, source.chapter_id)
        volume = self.planner_service.get_volume(project_id, source.volume_id)
        report = self.checks_service.get_latest_report(project_id, source.draft_id)
        if self._is_report_stale(report, source, aggregate, volume.version, chapter.version, scene.version):
            report = self.checks_service.run_for_draft(project_id, source.draft_id, trigger="repair_preflight")
        return report

    def _is_report_stale(self, report, source: SceneDraft, aggregate, volume_version: int, chapter_version: int, scene_version: int) -> bool:
        if report is None:
            return True
        if report.trigger == "generate_auto":
            return True
        versions = report.source_versions
        return any(
            [
                versions.story_bible_version != aggregate.story_bible.version,
                versions.characters_version != aggregate.characters.version,
                versions.world_version != aggregate.world.version,
                versions.power_system_version != aggregate.power_system.version,
                versions.volume_version != volume_version,
                versions.chapter_version != chapter_version,
                versions.scene_version != scene_version,
                versions.draft_updated_at != source.updated_at,
            ]
        )

    def _select_target_issues(self, report: SceneDraftCheckReport, issue_ids: list[str] | None) -> list[ConsistencyIssue]:
        open_issues = [issue for issue in report.issues if issue.status == "open"]
        if issue_ids is not None:
            requested = set(issue_ids)
            available_ids = {issue.issue_id for issue in open_issues}
            if not requested.issubset(available_ids):
                raise ValueError("issue_ids must reference open issues from the latest report.")
            filtered = [issue for issue in open_issues if issue.issue_id in requested]
        else:
            filtered = [issue for issue in open_issues if issue.issue_type != "style_constraint"]
        blockers = [issue for issue in filtered if issue.severity == "blocker"]
        warnings = [issue for issue in filtered if issue.severity == "warning"]
        return blockers + warnings

    def _load_fresh_bundle(self, project_id: str, source: SceneDraft) -> ContextBundle:
        bundle = self.scene_draft_service.get_context_bundle_for_draft(project_id, source.draft_id)
        if bundle is not None:
            return bundle
        return self.context_bundle_service.build(project_id, source.scene_id)

    def _generate_repaired_content(
        self,
        source: SceneDraft,
        bundle: ContextBundle,
        scene,
        issues: list[ConsistencyIssue],
    ) -> tuple[str, str]:
        if isinstance(self.llm_gateway, MockLLMGateway):
            content_md, summary = self._apply_mock_targeted_repair(source, bundle, scene, issues)
        else:
            try:
                content_md, summary = self._apply_openai_targeted_repair(source, bundle, scene, issues)
            except Exception:
                content_md, summary = self._apply_mock_targeted_repair(source, bundle, scene, issues)
        if self.style_service is not None:
            content_md, summary = self.style_service.sanitize_text(
                content_md,
                summary,
                bundle.style_constraints,
                protected_phrases=self.scene_draft_service._protected_phrases(bundle),
            )
        return content_md, summary

    def _apply_mock_targeted_repair(
        self,
        source: SceneDraft,
        bundle: ContextBundle,
        scene,
        issues: list[ConsistencyIssue],
    ) -> tuple[str, str]:
        content = source.content_md
        summary = source.summary
        briefs_by_id = {brief.character_id: brief for brief in bundle.character_briefs}
        target_location = bundle.location_brief.name if bundle.location_brief else ""

        for issue in issues:
            if issue.rule_id != "scene.forbidden.hit":
                continue
            phrase = self._evidence_value(issue, "forbidden")
            if phrase:
                content = content.replace(phrase, "")
                summary = summary.replace(phrase, "")

        for issue in issues:
            if issue.rule_id != "scene.must_include.missing":
                continue
            phrase = self._evidence_value(issue, "must_include")
            if phrase and phrase not in content:
                content = self._append_line(content, f"补入必含：{phrase}")

        field_map = [
            ("scene.goal.missing", "场景目标", scene.goal),
            ("scene.turning_point.missing", "场景转折", scene.turning_point),
            ("scene.outcome.missing", "场景结果", scene.outcome),
        ]
        for rule_id, label, phrase in field_map:
            if not phrase:
                continue
            if any(issue.rule_id == rule_id for issue in issues) and phrase not in content:
                content = self._append_line(content, f"{label}：{phrase}")

        character_issue_ids: set[str] = set()
        for issue in issues:
            if issue.rule_id not in {"character.protagonist.missing", "character.participant.missing"}:
                continue
            character_id = self._evidence_value(issue, "character_id")
            if not character_id or character_id in character_issue_ids:
                continue
            character_issue_ids.add(character_id)
            name = briefs_by_id.get(character_id).name if character_id in briefs_by_id else self._evidence_value(issue, "name")
            if name and name not in content:
                content = self._append_line(content, f"人物出场：{name}")

        if any(issue.rule_id == "timeline.time_anchor.missing" for issue in issues) and scene.time_anchor and scene.time_anchor not in content:
            content = self._append_line(content, f"时间锚：{scene.time_anchor}")

        for issue in issues:
            if issue.rule_id not in {"world.location.conflict", "world.location.mixed"}:
                continue
            other_locations = self._split_values(self._evidence_value(issue, "other_locations"))
            for other in other_locations:
                if other:
                    content = content.replace(other, target_location)
                    summary = summary.replace(other, target_location)
            if target_location and target_location not in content:
                content = self._append_line(content, f"地点：{target_location}")

        for issue in issues:
            if issue.rule_id != "power.realm.conflict":
                continue
            for realm in self._split_values(self._evidence_value(issue, "realms")):
                if realm:
                    content = content.replace(realm, "")
                    summary = summary.replace(realm, "")

        return self._normalize_text_block(content), self._normalize_text_block(summary)

    def _apply_openai_targeted_repair(
        self,
        source: SceneDraft,
        bundle: ContextBundle,
        scene,
        issues: list[ConsistencyIssue],
    ) -> tuple[str, str]:
        prompt = json.dumps(
            {
                "task": "Apply minimal targeted repair to the draft. Only fix the listed issues. Do not rewrite freely.",
                "draft": {"summary": source.summary, "content_md": source.content_md},
                "scene_anchor": bundle.scene_anchor.model_dump(mode="json"),
                "chapter_anchor": bundle.chapter_anchor.model_dump(mode="json"),
                "volume_anchor": bundle.volume_anchor.model_dump(mode="json"),
                "character_briefs": [brief.model_dump(mode="json") for brief in bundle.character_briefs],
                "location_brief": bundle.location_brief.model_dump(mode="json") if bundle.location_brief else None,
                "issues": [issue.model_dump(mode="json") for issue in issues],
                "constraints": [
                    "Only modify content_md and summary.",
                    "Do not modify canonical plans or memory.",
                    "Keep structure stable and perform minimal edits.",
                ],
            },
            ensure_ascii=False,
        )
        payload = self.llm_gateway.generate_text(
            GenerateRequest(
                system_prompt="Return JSON with summary and content_md fields only.",
                prompt=prompt,
            )
        )
        parsed = json.loads(payload)
        content_md = str(parsed.get("content_md", "")).strip()
        summary = str(parsed.get("summary", "")).strip()
        if not content_md:
            raise ValueError("Empty repair content")
        return content_md, summary

    def _evidence_value(self, issue: ConsistencyIssue, key: str) -> str:
        for evidence in issue.evidence_refs:
            if key in evidence:
                return str(evidence[key])
        return ""

    def _split_values(self, value: str) -> list[str]:
        if not value:
            return []
        return [part.strip() for part in value.split("、") if part.strip()]

    def _append_line(self, text: str, line: str) -> str:
        clean = text.rstrip()
        if not clean:
            return line
        return f"{clean}\n{line}"

    def _normalize_text_block(self, text: str) -> str:
        lines = [line.rstrip() for line in text.replace("\r\n", "\n").split("\n")]
        normalized: list[str] = []
        previous_blank = False
        for line in lines:
            if line.strip():
                normalized.append(line)
                previous_blank = False
            elif not previous_blank:
                normalized.append("")
                previous_blank = True
        return "\n".join(normalized).strip()

    def _cleanup_created_paths(self, created_paths: list[Path]) -> None:
        for path in reversed(created_paths):
            try:
                if self.file_repository.exists(path):
                    path.unlink()
            except Exception:
                pass

    def _manifest_item_from_draft(self, draft: SceneDraft) -> SceneDraftManifestItem:
        return SceneDraftManifestItem(
            draft_id=draft.draft_id,
            draft_no=draft.draft_no,
            status=draft.status,
            candidate_mode=draft.candidate_mode,
            summary=draft.summary,
            draft_path=draft.draft_path or "",
            context_bundle_path=draft.context_bundle_path,
            created_at=draft.created_at,
            accepted_at=draft.accepted_at,
            rejected_at=draft.rejected_at,
        )

    def _write_draft(self, slug: str, draft: SceneDraft) -> None:
        if draft.draft_path:
            path = self.paths.project_root(slug) / draft.draft_path
        else:
            path = self.paths.scene_draft_path(slug, draft.scene_id, draft.draft_no)
            draft.draft_path = self.paths.relative_to_project(slug, path)
        self.file_repository.write_json(path, draft.model_dump(mode="json"))

    def _write_manifest(self, slug: str, scene_id: str, manifest: SceneDraftManifest) -> None:
        self.file_repository.write_json(self.paths.scene_draft_manifest_path(slug, scene_id), manifest.model_dump(mode="json"))

    def _require_project(self, project_id: str) -> dict[str, object]:
        project = self.sqlite_repository.get_project_record(project_id)
        if project is None:
            raise KeyError(project_id)
        return project

    def _model_name(self) -> str:
        return "mock" if isinstance(self.llm_gateway, MockLLMGateway) else getattr(self.llm_gateway, "model_name", "openai")
