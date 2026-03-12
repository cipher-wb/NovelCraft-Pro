from __future__ import annotations

import re
import uuid
from dataclasses import dataclass

from backend.app.domain.models.common import utc_now
from backend.app.domain.models.issues import ConsistencyIssue
from backend.app.domain.models.planning import ChapterPlan, ScenePlan, VolumePlan
from backend.app.domain.models.project import CharacterDocument, PowerSystemDocument, StoryBible, WorldDocument
from backend.app.domain.models.writing import ContextBundle

_SPLIT_PATTERN = re.compile(r"[\s,，。！？!?:：;；、/\\\-()（）\[\]{}\"'“”‘’]+")
_WHITESPACE_PATTERN = re.compile(r"\s+")


@dataclass(slots=True)
class CheckInputContext:
    project_id: str
    draft_id: str
    checker_run_id: str = "check_run_test"
    draft_text: str = ""
    draft_summary: str = ""
    story_bible: StoryBible | None = None
    characters: CharacterDocument | None = None
    world: WorldDocument | None = None
    power_system: PowerSystemDocument | None = None
    volume: VolumePlan | None = None
    chapter: ChapterPlan | None = None
    scene: ScenePlan | None = None
    context_bundle: ContextBundle | None = None


class LiteralMatchingMixin:
    def _normalize_text(self, value: str) -> str:
        lowered = value.lower().replace("\u3000", " ")
        return _WHITESPACE_PATTERN.sub(" ", lowered).strip()

    def _contains_literal_phrase(self, text: str, phrase: str) -> bool:
        normalized_text = self._normalize_text(text)
        normalized_phrase = self._normalize_text(phrase)
        if not normalized_text or not normalized_phrase:
            return False
        return normalized_phrase in normalized_text

    def _extract_keywords(self, phrase: str) -> list[str]:
        normalized_phrase = self._normalize_text(phrase)
        if not normalized_phrase:
            return []
        keywords: list[str] = []
        seen: set[str] = set()
        for token in _SPLIT_PATTERN.split(normalized_phrase):
            token = token.strip()
            if len(token) < 2 or token in seen:
                continue
            seen.add(token)
            keywords.append(token)
        return keywords

    def _contains_phrase_or_keywords(self, text: str, phrase: str) -> bool:
        if self._contains_literal_phrase(text, phrase):
            return True
        normalized_text = self._normalize_text(text)
        for keyword in self._extract_keywords(phrase):
            if keyword in normalized_text:
                return True
        return False

    def _build_issue(
        self,
        input_ctx: CheckInputContext,
        *,
        issue_type: str,
        rule_id: str,
        severity: str,
        title: str,
        description: str,
        evidence_refs: list[dict[str, str]] | None = None,
        suggested_fix: list[str] | None = None,
    ) -> ConsistencyIssue:
        return ConsistencyIssue(
            issue_id=f"issue_{uuid.uuid4().hex[:12]}",
            project_id=input_ctx.project_id,
            issue_type=issue_type,
            rule_id=rule_id,
            severity=severity,
            status="open",
            source_scope="scene_draft",
            source_id=input_ctx.draft_id,
            title=title,
            description=description,
            evidence_refs=evidence_refs or [],
            suggested_fix=suggested_fix or [],
            checker_run_id=input_ctx.checker_run_id,
            detected_at=utc_now(),
        )


class SceneAlignmentEvaluator(LiteralMatchingMixin):
    rule_family = "scene_alignment"

    def evaluate(self, input_ctx: CheckInputContext) -> list[ConsistencyIssue]:
        scene = input_ctx.scene
        if scene is None:
            return []
        draft_text = f"{input_ctx.draft_summary}\n{input_ctx.draft_text}"
        issues: list[ConsistencyIssue] = []
        checks = [
            ("goal", scene.goal, "blocker", "scene.goal.missing", "场景目标未命中草稿"),
            ("obstacle", scene.obstacle, "warning", "scene.obstacle.missing", "场景阻碍未命中草稿"),
            ("turning_point", scene.turning_point, "blocker", "scene.turning_point.missing", "场景转折未命中草稿"),
            ("outcome", scene.outcome, "blocker", "scene.outcome.missing", "场景结果未命中草稿"),
        ]
        for field_name, phrase, severity, rule_id, title in checks:
            if phrase and not self._contains_phrase_or_keywords(draft_text, phrase):
                issues.append(
                    self._build_issue(
                        input_ctx,
                        issue_type="scene_alignment",
                        rule_id=rule_id,
                        severity=severity,
                        title=title,
                        description=f"ScenePlan.{field_name} 未在当前 draft 中按字面短语或关键词命中。",
                        evidence_refs=[{"field": field_name, "value": phrase}],
                        suggested_fix=[f"在草稿中补入与 {field_name} 对齐的明确表述。"],
                    )
                )
        for phrase in scene.must_include:
            if phrase and not self._contains_literal_phrase(draft_text, phrase):
                issues.append(
                    self._build_issue(
                        input_ctx,
                        issue_type="scene_alignment",
                        rule_id="scene.must_include.missing",
                        severity="blocker",
                        title="必含短语缺失",
                        description="ScenePlan.must_include 中的字面短语未出现在当前 draft。",
                        evidence_refs=[{"field": "must_include", "value": phrase}],
                        suggested_fix=[f"将短语“{phrase}”直接写入草稿。"],
                    )
                )
        for phrase in scene.forbidden:
            if phrase and self._contains_literal_phrase(draft_text, phrase):
                issues.append(
                    self._build_issue(
                        input_ctx,
                        issue_type="scene_alignment",
                        rule_id="scene.forbidden.hit",
                        severity="blocker",
                        title="命中禁止短语",
                        description="ScenePlan.forbidden 中的字面短语出现在当前 draft。",
                        evidence_refs=[{"field": "forbidden", "value": phrase}],
                        suggested_fix=[f"移除或改写短语“{phrase}”。"],
                    )
                )
        return issues


class CharacterConsistencyEvaluator(LiteralMatchingMixin):
    rule_family = "character_consistency"

    def evaluate(self, input_ctx: CheckInputContext) -> list[ConsistencyIssue]:
        scene = input_ctx.scene
        characters = input_ctx.characters
        story_bible = input_ctx.story_bible
        if scene is None or characters is None or story_bible is None:
            return []
        draft_text = f"{input_ctx.draft_summary}\n{input_ctx.draft_text}"
        cards = {item.character_id: item for item in characters.items if item.character_id in scene.character_ids}
        token_map: dict[str, set[str]] = {}
        for character in cards.values():
            for token in [character.name, *character.aliases]:
                normalized = self._normalize_text(token)
                if not normalized:
                    continue
                token_map.setdefault(normalized, set()).add(character.character_id)

        matched_character_ids: set[str] = set()
        for token, character_ids in token_map.items():
            if len(character_ids) != 1:
                continue
            if token in self._normalize_text(draft_text):
                matched_character_ids.update(character_ids)

        issues: list[ConsistencyIssue] = []
        protagonist_ids = set(story_bible.protagonist_ids)
        for character_id in scene.character_ids:
            if character_id in matched_character_ids:
                continue
            card = cards.get(character_id)
            if card is None:
                continue
            is_protagonist = card.is_protagonist or character_id in protagonist_ids or card.role == "protagonist"
            if is_protagonist:
                issues.append(
                    self._build_issue(
                        input_ctx,
                        issue_type="character_consistency",
                        rule_id="character.protagonist.missing",
                        severity="blocker",
                        title="主角未出场",
                        description=f"主角 {card.name} 未以唯一 name/alias 命中当前 draft。",
                        evidence_refs=[{"character_id": card.character_id, "name": card.name}],
                        suggested_fix=[f"明确写出 {card.name} 或仅归属于他的唯一别名。"],
                    )
                )
            else:
                issues.append(
                    self._build_issue(
                        input_ctx,
                        issue_type="character_consistency",
                        rule_id="character.participant.missing",
                        severity="warning",
                        title="参演角色未出场",
                        description=f"ScenePlan.character_ids 中的角色 {card.name} 未以唯一 name/alias 命中当前 draft。",
                        evidence_refs=[{"character_id": card.character_id, "name": card.name}],
                        suggested_fix=[f"如该角色应出场，请显式写出 {card.name} 或唯一别名。"],
                    )
                )
        return issues


class TimelineOrderEvaluator(LiteralMatchingMixin):
    rule_family = "timeline_order"

    def evaluate(self, input_ctx: CheckInputContext) -> list[ConsistencyIssue]:
        scene = input_ctx.scene
        chapter = input_ctx.chapter
        bundle = input_ctx.context_bundle
        if scene is None or chapter is None or bundle is None:
            return []
        issues: list[ConsistencyIssue] = []
        for recent in bundle.retrieved_memory.recent_scene_summaries:
            if recent.chapter_id != chapter.chapter_id or recent.scene_no >= scene.scene_no:
                issues.append(
                    self._build_issue(
                        input_ctx,
                        issue_type="timeline_order",
                        rule_id="timeline.recent_scene.order",
                        severity="blocker",
                        title="最近场景顺序异常",
                        description="retrieved recent_scene_summaries 中存在不早于当前 scene 的记录。",
                        evidence_refs=[{"scene_id": recent.scene_id, "scene_no": str(recent.scene_no)}],
                        suggested_fix=["重新检查 retrieval 顺序或重跑 memory ingest。"],
                    )
                )
                break
        previous = bundle.retrieved_memory.previous_chapter_summary
        if previous is not None and previous.chapter_no >= chapter.chapter_no:
            issues.append(
                self._build_issue(
                    input_ctx,
                    issue_type="timeline_order",
                    rule_id="timeline.previous_chapter.order",
                    severity="blocker",
                    title="上一章摘要顺序异常",
                    description="previous_chapter_summary 指向的 chapter_no 不早于当前 chapter。",
                    evidence_refs=[{"chapter_id": previous.chapter_id, "chapter_no": str(previous.chapter_no)}],
                    suggested_fix=["重新检查 chapter summary retrieval 选择逻辑。"],
                )
            )
        if scene.time_anchor and not self._contains_literal_phrase(input_ctx.draft_text, scene.time_anchor):
            issues.append(
                self._build_issue(
                    input_ctx,
                    issue_type="timeline_order",
                    rule_id="timeline.time_anchor.missing",
                    severity="warning",
                    title="时间锚未命中草稿",
                    description="ScenePlan.time_anchor 非空，但未在 draft 中字面出现。",
                    evidence_refs=[{"time_anchor": scene.time_anchor}],
                    suggested_fix=[f"在草稿中显式写出时间锚“{scene.time_anchor}”。"],
                )
            )
        return issues


class WorldPowerConflictEvaluator(LiteralMatchingMixin):
    rule_family = "world_power_conflict"

    def evaluate(self, input_ctx: CheckInputContext) -> list[ConsistencyIssue]:
        scene = input_ctx.scene
        world = input_ctx.world
        power_system = input_ctx.power_system
        characters = input_ctx.characters
        if scene is None or world is None or power_system is None or characters is None:
            return []
        issues: list[ConsistencyIssue] = []
        draft_text = input_ctx.draft_text

        target_location = next((item for item in world.locations if item.location_id == scene.location_id), None)
        if target_location is not None:
            target_hit = self._contains_literal_phrase(draft_text, target_location.name)
            other_hits = [item.name for item in world.locations if item.location_id != scene.location_id and self._contains_literal_phrase(draft_text, item.name)]
            if other_hits and not target_hit:
                issues.append(
                    self._build_issue(
                        input_ctx,
                        issue_type="world_power_conflict",
                        rule_id="world.location.conflict",
                        severity="blocker",
                        title="地点硬冲突",
                        description="草稿命中了其他 canonical 地点名，但未命中目标地点名。",
                        evidence_refs=[{"target_location": target_location.name, "other_locations": "、".join(other_hits)}],
                        suggested_fix=[f"显式写出目标地点“{target_location.name}”，或移除冲突地点。"],
                    )
                )
            elif other_hits and target_hit:
                issues.append(
                    self._build_issue(
                        input_ctx,
                        issue_type="world_power_conflict",
                        rule_id="world.location.mixed",
                        severity="warning",
                        title="地点混用",
                        description="草稿同时命中了目标地点名和其他 canonical 地点名。",
                        evidence_refs=[{"target_location": target_location.name, "other_locations": "、".join(other_hits)}],
                        suggested_fix=["确认当前 scene 是否需要多个地点；若不需要，请消除混用。"],
                    )
                )

        canonical_realms = [item.name for item in power_system.realm_ladder if item.name]
        character_map = {item.character_id: item for item in characters.items}
        allowed_realms = {
            character_map[character_id].realm_level
            for character_id in scene.character_ids
            if character_id in character_map and character_map[character_id].realm_level
        }
        for phrase in [scene.outcome, *scene.must_include]:
            for realm_name in canonical_realms:
                if self._contains_literal_phrase(phrase, realm_name):
                    allowed_realms.add(realm_name)
        conflicting_realms = [
            realm_name
            for realm_name in canonical_realms
            if realm_name not in allowed_realms and self._contains_literal_phrase(draft_text, realm_name)
        ]
        if conflicting_realms:
            issues.append(
                self._build_issue(
                    input_ctx,
                    issue_type="world_power_conflict",
                    rule_id="power.realm.conflict",
                    severity="warning",
                    title="境界字面不一致",
                    description="草稿命中了不在当前允许范围内的 canonical 境界名。",
                    evidence_refs=[{"realms": "、".join(conflicting_realms)}],
                    suggested_fix=["确认这些境界是否应出现在当前 scene；若不是，请改写或删除。"],
                )
            )
        return issues
