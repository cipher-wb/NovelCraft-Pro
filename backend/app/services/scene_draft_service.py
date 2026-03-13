from __future__ import annotations

import json
import uuid
from typing import Any

from backend.app.core.paths import AppPaths
from backend.app.domain.models.common import DraftStatus, utc_now
from backend.app.domain.models.issues import SceneDraftCheckReport
from backend.app.domain.models.writing import ContextBundle, SceneDraft, SceneDraftManifest, SceneDraftManifestItem
from backend.app.infra.llm_gateway import GenerateRequest, MockLLMGateway
from backend.app.repositories.file_repository import FileRepository
from backend.app.repositories.sqlite_repository import SQLiteRepository
from backend.app.services.bible_service import BibleService
from backend.app.services.checks_service import ChecksService
from backend.app.services.context_bundle_service import ContextBundleService
from backend.app.services.exceptions import ConflictError
from backend.app.services.memory_service import MemoryService
from backend.app.services.planner_service import PlannerService
from backend.app.services.style_service import StyleService


class SceneDraftService:
    def __init__(
        self,
        paths: AppPaths,
        file_repository: FileRepository,
        sqlite_repository: SQLiteRepository,
        bible_service: BibleService,
        planner_service: PlannerService,
        context_bundle_service: ContextBundleService,
        memory_service: MemoryService,
        checks_service: ChecksService,
        style_service: StyleService | None,
        llm_gateway,
    ) -> None:
        self.paths = paths
        self.file_repository = file_repository
        self.sqlite_repository = sqlite_repository
        self.bible_service = bible_service
        self.planner_service = planner_service
        self.context_bundle_service = context_bundle_service
        self.memory_service = memory_service
        self.checks_service = checks_service
        self.style_service = style_service
        self.llm_gateway = llm_gateway

    def generate(self, project_id: str, scene_id: str, mode: str) -> SceneDraft:
        if mode not in {"outline_strict", "momentum"}:
            raise ValueError("Unsupported draft generation mode.")
        project = self._require_project(project_id)
        slug = project["slug"]
        self._ensure_ready_generation_inputs(project_id, scene_id)
        scene = self.planner_service.get_scene(project_id, scene_id)
        chapter = self.planner_service.get_chapter(project_id, scene.chapter_id)
        volume = self.planner_service.get_volume(project_id, scene.volume_id)
        manifest = self.get_scene_manifest(project_id, scene_id)

        updated_existing_drafts: list[SceneDraft] = []
        for item in manifest.items:
            if item.status != DraftStatus.draft.value:
                continue
            existing = self.get_draft(project_id, item.draft_id)
            existing.status = DraftStatus.superseded.value
            existing.updated_at = utc_now()
            updated_existing_drafts.append(existing)

        draft_no = manifest.last_draft_no + 1
        bundle = self.context_bundle_service.build(project_id, scene_id)
        bundle_path = self.paths.scene_context_bundle_path(slug, scene_id, draft_no)
        self.file_repository.write_json(bundle_path, bundle.model_dump(mode="json"))

        content_md, summary = self._generate_content(bundle, mode)
        now = utc_now()
        draft_path = self.paths.scene_draft_path(slug, scene_id, draft_no)
        draft = SceneDraft(
            draft_id=f"draft_{uuid.uuid4().hex[:12]}",
            project_id=project_id,
            volume_id=scene.volume_id,
            chapter_id=scene.chapter_id,
            scene_id=scene.scene_id,
            chapter_no=scene.chapter_no,
            scene_no=scene.scene_no,
            draft_no=draft_no,
            operation="generate",
            candidate_mode=mode,
            status=DraftStatus.draft.value,
            content_md=content_md,
            summary=summary,
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
            supersedes_draft_id=manifest.latest_draft_id,
            memory_stub_record_id=None,
        )
        self.file_repository.write_json(draft_path, draft.model_dump(mode="json"))

        for existing in updated_existing_drafts:
            self._write_draft(slug, existing)

        manifest.items = [self._manifest_item_from_draft(self.get_draft(project_id, item.draft_id)) for item in manifest.items]
        manifest.items = [item for item in manifest.items if item.draft_id not in {d.draft_id for d in updated_existing_drafts}] + [
            self._manifest_item_from_draft(d) for d in updated_existing_drafts
        ]
        manifest.items = [item for item in manifest.items if item.draft_id != draft.draft_id]
        manifest.items.append(self._manifest_item_from_draft(draft))
        manifest.items = sorted(manifest.items, key=lambda value: value.draft_no)
        manifest.latest_draft_id = draft.draft_id
        manifest.last_draft_no = draft_no
        manifest.version += 1
        manifest.updated_at = now
        self._write_manifest(slug, scene_id, manifest)
        self.checks_service.run_for_draft(project_id, draft.draft_id, trigger="generate_auto")
        return self.get_draft(project_id, draft.draft_id)

    def get_scene_manifest(self, project_id: str, scene_id: str) -> SceneDraftManifest:
        project = self._require_project(project_id)
        slug = project["slug"]
        path = self.paths.scene_draft_manifest_path(slug, scene_id)
        if self.file_repository.exists(path):
            return SceneDraftManifest.model_validate(self.file_repository.read_json(path))
        scene = self.planner_service.get_scene(project_id, scene_id)
        manifest = SceneDraftManifest(
            project_id=project_id,
            volume_id=scene.volume_id,
            chapter_id=scene.chapter_id,
            scene_id=scene.scene_id,
            updated_at=utc_now(),
        )
        self._write_manifest(slug, scene_id, manifest)
        return manifest

    def get_draft(self, project_id: str, draft_id: str) -> SceneDraft:
        project = self._require_project(project_id)
        slug = project["slug"]
        for scene_dir in sorted(self.paths.scene_drafts_root(slug).glob("*")):
            if not scene_dir.is_dir():
                continue
            for draft_path in sorted(scene_dir.glob("draft-*.json")):
                draft = SceneDraft.model_validate(self.file_repository.read_json(draft_path))
                if draft.draft_id == draft_id:
                    return draft
        raise KeyError(draft_id)

    def get_context_bundle_for_draft(self, project_id: str, draft_id: str) -> ContextBundle | None:
        project = self._require_project(project_id)
        slug = project["slug"]
        draft = self.get_draft(project_id, draft_id)
        if draft.context_bundle_path:
            path = self.paths.project_root(slug) / draft.context_bundle_path
            if self.file_repository.exists(path):
                try:
                    return ContextBundle.model_validate(self.file_repository.read_json(path))
                except Exception:
                    pass
        try:
            return self.context_bundle_service.build(project_id, draft.scene_id)
        except Exception:
            return None

    def get_latest_check_report(self, project_id: str, draft_id: str) -> SceneDraftCheckReport | None:
        return self.checks_service.get_latest_report(project_id, draft_id)

    def recheck_checks(self, project_id: str, draft_id: str) -> SceneDraftCheckReport:
        return self.checks_service.run_for_draft(project_id, draft_id, trigger="manual_recheck")

    def accept(self, project_id: str, draft_id: str) -> SceneDraft:
        project = self._require_project(project_id)
        slug = project["slug"]
        draft = self.get_draft(project_id, draft_id)
        if draft.status != DraftStatus.draft.value:
            raise ConflictError("Only draft status can be accepted.")
        self._ensure_ready_generation_inputs(project_id, draft.scene_id)

        scene = self.planner_service.get_scene(project_id, draft.scene_id)
        chapter = self.planner_service.get_chapter(project_id, draft.chapter_id)
        volume = self.planner_service.get_volume(project_id, draft.volume_id)
        if (
            draft.source_scene_version != scene.version
            or draft.source_chapter_version != chapter.version
            or draft.source_volume_version != volume.version
        ):
            raise ConflictError("Draft source versions do not match current canonical state.")
        self.checks_service.ensure_accept_allowed(project_id, draft_id)
        draft = self.get_draft(project_id, draft_id)

        manifest = self.get_scene_manifest(project_id, draft.scene_id)
        sibling_drafts = [self.get_draft(project_id, item.draft_id) for item in manifest.items if item.draft_id != draft_id]
        now = utc_now()
        for sibling in sibling_drafts:
            if sibling.status in {DraftStatus.draft.value, DraftStatus.accepted.value}:
                sibling.status = DraftStatus.superseded.value
                sibling.updated_at = now
                self._write_draft(slug, sibling)

        draft.status = DraftStatus.accepted.value
        draft.accepted_at = now
        draft.updated_at = now
        ingest_result = self.memory_service.ingest_accepted_draft(slug, draft, scene, chapter, volume)
        draft.memory_stub_record_id = ingest_result.accepted_scene_item.memory_id
        self._write_draft(slug, draft)

        manifest.items = [self._manifest_item_from_draft(self.get_draft(project_id, item.draft_id)) for item in manifest.items]
        manifest.items = sorted(manifest.items, key=lambda value: value.draft_no)
        manifest.accepted_draft_id = draft.draft_id
        manifest.version += 1
        manifest.updated_at = now
        self._write_manifest(slug, draft.scene_id, manifest)
        return draft

    def reject(self, project_id: str, draft_id: str) -> SceneDraft:
        project = self._require_project(project_id)
        slug = project["slug"]
        draft = self.get_draft(project_id, draft_id)
        if draft.status != DraftStatus.draft.value:
            raise ConflictError("Only draft status can be rejected.")

        now = utc_now()
        draft.status = DraftStatus.rejected.value
        draft.rejected_at = now
        draft.updated_at = now
        self._write_draft(slug, draft)

        manifest = self.get_scene_manifest(project_id, draft.scene_id)
        manifest.items = [self._manifest_item_from_draft(self.get_draft(project_id, item.draft_id)) for item in manifest.items]
        manifest.items = sorted(manifest.items, key=lambda value: value.draft_no)
        manifest.version += 1
        manifest.updated_at = now
        self._write_manifest(slug, draft.scene_id, manifest)
        return draft

    def _ensure_ready_generation_inputs(self, project_id: str, scene_id: str) -> None:
        aggregate = self.bible_service.get_bible_aggregate(project_id)
        scene = self.planner_service.get_scene(project_id, scene_id)
        chapter = self.planner_service.get_chapter(project_id, scene.chapter_id)
        volume = self.planner_service.get_volume(project_id, scene.volume_id)
        statuses = {
            "story_bible": aggregate.story_bible.status,
            "characters": aggregate.characters.status,
            "world": aggregate.world.status,
            "power_system": aggregate.power_system.status,
            "volume": volume.status,
            "chapter": chapter.status,
            "scene": scene.status,
        }
        not_ready = [name for name, value in statuses.items() if value != "ready"]
        if not_ready:
            raise ConflictError(f"Generation prerequisites are not ready: {', '.join(not_ready)}")

    def _generate_content(self, bundle: ContextBundle, mode: str) -> tuple[str, str]:
        if isinstance(self.llm_gateway, MockLLMGateway):
            content_md, summary = self._generate_mock_content(bundle, mode)
        else:
            payload = self.llm_gateway.generate_text(
                GenerateRequest(
                    system_prompt="Return JSON with summary and content_md fields.",
                    prompt=self._build_generation_prompt(bundle, mode),
                )
            )
            try:
                parsed = json.loads(payload)
                summary = str(parsed.get("summary", "")).strip() or self._deterministic_summary(bundle)
                content_md = str(parsed.get("content_md", "")).strip()
                if not content_md:
                    raise ValueError("Empty content")
            except Exception:
                content_md, summary = payload.strip(), self._deterministic_summary(bundle)
        if self.style_service is not None:
            content_md, summary = self.style_service.sanitize_text(
                content_md,
                summary,
                bundle.style_constraints,
                protected_phrases=self._protected_phrases(bundle),
            )
        return content_md, summary

    def _generate_mock_content(self, bundle: ContextBundle, mode: str) -> tuple[str, str]:
        location_name = bundle.location_brief.name if bundle.location_brief else "未明地点"
        names = "、".join(item.name for item in bundle.character_briefs) or "无登场角色"
        previous = bundle.continuity.previous_accepted_scene_summary or "无前序 accepted 摘要"
        burst = bundle.style_constraints.global_constraints.sentence_rhythm.burst_short_lines
        payoff_direct = bundle.style_constraints.global_constraints.payoff_style.intensity == "direct"
        opener = "压强前推" if mode == "momentum" else "按提纲推进"
        ending = "结果直接落到" if payoff_direct else "结果收束到"
        body_line = (
            f"正文：{opener}，围绕“{bundle.scene_anchor.goal}”展开，先遭遇“{bundle.scene_anchor.obstacle}”，"
            f"随后在“{bundle.scene_anchor.turning_point}”发生变化，最终{ending}“{bundle.scene_anchor.outcome}”。"
        )
        lines = [
            f"# {bundle.scene_anchor.title}",
            f"模式：{mode}",
            f"承诺：{bundle.story_anchor.story_promise}",
            f"章节目的：{bundle.chapter_anchor.purpose}",
            f"地点：{location_name}",
            f"角色：{names}",
            f"连续性：{previous}",
            f"场景目标：{bundle.scene_anchor.goal}",
            f"阻碍：{bundle.scene_anchor.obstacle}",
            f"转折：{bundle.scene_anchor.turning_point}",
            f"结果：{bundle.scene_anchor.outcome}",
            f"必含：{'、'.join(bundle.scene_anchor.must_include) if bundle.scene_anchor.must_include else '无'}",
        ]
        if burst:
            lines.extend(
                [
                    f"正文：{opener}。",
                    f"先奔着“{bundle.scene_anchor.goal}”去。",
                    f"先撞上“{bundle.scene_anchor.obstacle}”。",
                    f"再在“{bundle.scene_anchor.turning_point}”翻面。",
                    f"{ending}“{bundle.scene_anchor.outcome}”。",
                ]
            )
        else:
            lines.append(body_line)
        content_md = "\n".join(lines)
        return content_md, self._deterministic_summary(bundle)

    def _deterministic_summary(self, bundle: ContextBundle) -> str:
        return (
            f"{bundle.scene_anchor.title}：{bundle.scene_anchor.goal}，遭遇{bundle.scene_anchor.obstacle}，"
            f"在{bundle.scene_anchor.turning_point}后走向{bundle.scene_anchor.outcome}。"
        )

    def _build_generation_prompt(self, bundle: ContextBundle, mode: str) -> str:
        return json.dumps(
            {
                "mode": mode,
                "story_anchor": bundle.story_anchor.model_dump(mode="json"),
                "volume_anchor": bundle.volume_anchor.model_dump(mode="json"),
                "chapter_anchor": bundle.chapter_anchor.model_dump(mode="json"),
                "scene_anchor": bundle.scene_anchor.model_dump(mode="json"),
                "character_briefs": [item.model_dump(mode="json") for item in bundle.character_briefs],
                "faction_briefs": [item.model_dump(mode="json") for item in bundle.faction_briefs],
                "location_brief": bundle.location_brief.model_dump(mode="json") if bundle.location_brief else None,
                "power_brief": bundle.power_brief.model_dump(mode="json") if bundle.power_brief else None,
                "continuity": bundle.continuity.model_dump(mode="json"),
                "style_constraints": bundle.style_constraints.model_dump(mode="json"),
                "retrieved_memory": bundle.retrieved_memory.model_dump(mode="json"),
            },
            ensure_ascii=False,
        )

    def _protected_phrases(self, bundle: ContextBundle) -> set[str]:
        protected = {phrase for phrase in [*bundle.scene_anchor.must_include, bundle.scene_anchor.goal, bundle.scene_anchor.turning_point, bundle.scene_anchor.outcome] if phrase}
        for brief in bundle.character_briefs:
            if brief.is_protagonist and brief.name:
                protected.add(brief.name)
        if bundle.location_brief and bundle.location_brief.name:
            protected.add(bundle.location_brief.name)
        return protected

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

    def _require_project(self, project_id: str) -> dict[str, Any]:
        project = self.sqlite_repository.get_project_record(project_id)
        if project is None:
            raise KeyError(project_id)
        return project

    def _model_name(self) -> str:
        return "mock" if isinstance(self.llm_gateway, MockLLMGateway) else getattr(self.llm_gateway, "model_name", "openai")


