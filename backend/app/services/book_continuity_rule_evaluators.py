from __future__ import annotations

import re
import uuid
from dataclasses import dataclass
from datetime import datetime

from backend.app.domain.models.issues import ConsistencyIssue
from backend.app.domain.models.planning import VolumePlan
from backend.app.domain.models.project import CharacterCard, CharacterDocument, PowerSystemDocument, StoryBible, WorldDocument
from backend.app.domain.models.writing import (
    AcceptedSceneMemoryDocument,
    BookAssembledDocument,
    BookSummaryMemoryDocument,
    ChapterSummariesMemoryDocument,
    CharacterStateSummariesMemoryDocument,
    VolumeAssembledDocument,
    VolumeSummariesMemoryDocument,
)

TOKEN_SPLIT_RE = re.compile(r"[\s\u3000,，.。!！?？;；:：/\\|()\[\]{}<>\"'“”‘’\-—_]+")
STOPWORDS = {
    "的",
    "了",
    "和",
    "与",
    "及",
    "是",
    "在",
    "中",
    "后",
    "前",
    "并",
    "并且",
    "以及",
    "一个",
    "一种",
    "这个",
    "那个",
    "目前",
    "当前",
    "目标",
    "冲突",
    "故事",
    "主线",
    "推进",
    "展开",
    "发展",
    "主角",
    "卷",
    "本卷",
    "the",
    "and",
    "for",
    "with",
    "from",
    "that",
    "this",
    "into",
    "then",
}


@dataclass(slots=True)
class FinalizedVolumeEntry:
    volume: VolumePlan
    artifact: VolumeAssembledDocument


@dataclass(slots=True)
class BookContinuityCheckInput:
    project_id: str
    checker_run_id: str
    detected_at: datetime
    story_bible: StoryBible
    characters: CharacterDocument
    world: WorldDocument
    power_system: PowerSystemDocument
    planned_volumes: list[VolumePlan]
    finalized_volumes: list[FinalizedVolumeEntry]
    book_assembled: BookAssembledDocument
    accepted_scenes: AcceptedSceneMemoryDocument
    chapter_summaries: ChapterSummariesMemoryDocument
    character_state_summaries: CharacterStateSummariesMemoryDocument
    volume_summaries: VolumeSummariesMemoryDocument
    book_summary: BookSummaryMemoryDocument


class _EvaluatorBase:
    issue_type = "continuity"

    def _issue(
        self,
        context: BookContinuityCheckInput,
        rule_id: str,
        severity: str,
        description: str,
    ) -> ConsistencyIssue:
        return ConsistencyIssue(
            issue_id=f"issue_{uuid.uuid4().hex[:12]}",
            project_id=context.project_id,
            issue_type=self.issue_type,
            rule_id=rule_id,
            severity=severity,
            status="open",
            source_scope="project",
            source_id=context.project_id,
            title=rule_id,
            description=description,
            checker_run_id=context.checker_run_id,
            detected_at=context.detected_at,
        )

    def _normalize(self, text: str) -> str:
        return " ".join(text.lower().split())

    def _tokenize(self, text: str) -> set[str]:
        normalized = self._normalize(text)
        tokens = {token for token in TOKEN_SPLIT_RE.split(normalized) if len(token) >= 2}
        return {token for token in tokens if token not in STOPWORDS}

    def _extract_digits(self, text: str) -> int | None:
        match = re.search(r"(\d+)", text)
        if match is None:
            return None
        return int(match.group(1))


class LongArcCharacterEvaluator(_EvaluatorBase):
    issue_type = "long_arc_character"

    def evaluate(self, context: BookContinuityCheckInput) -> list[ConsistencyIssue]:
        issues: list[ConsistencyIssue] = []
        scoped_volume_ids = {entry.volume.volume_id for entry in context.finalized_volumes}
        if not scoped_volume_ids:
            return issues

        appearances_by_character: dict[str, set[str]] = {}
        scoped_scene_presence: set[str] = set()
        has_structured_character_ids = False
        max_chapter_no = 0
        for item in context.accepted_scenes.items:
            if item.volume_id not in scoped_volume_ids:
                continue
            scoped_scene_presence.add(item.volume_id)
            max_chapter_no = max(max_chapter_no, item.chapter_no)
            for character_id in item.character_ids:
                has_structured_character_ids = True
                appearances_by_character.setdefault(character_id, set()).add(item.volume_id)

        protagonists = list(dict.fromkeys(context.story_bible.protagonist_ids))
        last_volume_id = context.finalized_volumes[-1].volume.volume_id
        character_by_id = {item.character_id: item for item in context.characters.items}

        for protagonist_id in protagonists:
            if not has_structured_character_ids and protagonist_id in character_by_id:
                seen_in = set(scoped_scene_presence)
            else:
                seen_in = appearances_by_character.get(protagonist_id, set())
            if not seen_in:
                issues.append(
                    self._issue(
                        context,
                        "continuity.character.protagonist.absent_all",
                        "blocker",
                        f"主角 {protagonist_id} 在当前整书 assembled 覆盖的 finalized volumes 中从未出现。",
                    )
                )
                continue
            if last_volume_id not in seen_in:
                issues.append(
                    self._issue(
                        context,
                        "continuity.character.protagonist.absent_latest",
                        "warning",
                        f"主角 {protagonist_id} 在最后一个 finalized volume 中缺席。",
                    )
                )

        for character in context.characters.items:
            if character.is_protagonist:
                continue
            first_hint = self._extract_digits(character.first_appearance_hint)
            if first_hint is None or first_hint > max_chapter_no:
                continue
            if character.character_id not in appearances_by_character:
                issues.append(
                    self._issue(
                        context,
                        "continuity.character.expected_missing",
                        "warning",
                        f"角色 {character.name or character.character_id} 已到应出现范围，但在当前 finalized volumes 中仍未出现。",
                    )
                )
        return issues


class WorldPowerCrossVolumeEvaluator(_EvaluatorBase):
    issue_type = "world_power_cross_volume"

    def evaluate(self, context: BookContinuityCheckInput) -> list[ConsistencyIssue]:
        issues: list[ConsistencyIssue] = []
        scoped_volume_ids = {entry.volume.volume_id for entry in context.finalized_volumes}
        if not scoped_volume_ids:
            return issues

        location_ids = {item.location_id for item in context.world.locations}
        realm_names = {item.name for item in context.power_system.realm_ladder}

        for item in context.accepted_scenes.items:
            if item.volume_id not in scoped_volume_ids or item.location_id is None:
                continue
            if item.location_id not in location_ids:
                issues.append(
                    self._issue(
                        context,
                        "continuity.world.location.invalid",
                        "blocker",
                        f"结构化 location_id {item.location_id} 不存在于 canonical world locations 中。",
                    )
                )

        appeared_character_ids = {
            character_id
            for item in context.accepted_scenes.items
            if item.volume_id in scoped_volume_ids
            for character_id in item.character_ids
        }
        protagonist_ids = set(context.story_bible.protagonist_ids)
        relevant_character_ids = appeared_character_ids | protagonist_ids
        for character in context.characters.items:
            if character.character_id not in relevant_character_ids:
                continue
            if character.realm_level and character.realm_level not in realm_names:
                issues.append(
                    self._issue(
                        context,
                        "continuity.power.realm.invalid",
                        "blocker",
                        f"角色 {character.name or character.character_id} 的 realm_level={character.realm_level} 不存在于 canonical realm ladder 中。",
                    )
                )

        protagonist_realms = {
            character.realm_level
            for character in context.characters.items
            if character.character_id in protagonist_ids and character.realm_level
        }
        if realm_names:
            for entry in context.finalized_volumes:
                text = f"{entry.artifact.summary} {entry.artifact.hook}"
                seen_realms = {realm for realm in realm_names if realm and realm in text}
                if seen_realms and protagonist_realms.isdisjoint(seen_realms):
                    issues.append(
                        self._issue(
                            context,
                            "continuity.power.realm.weak_conflict",
                            "warning",
                            f"卷 {entry.volume.volume_no} 的 summary/hook 中出现了与当前主角境界不一致的 canonical realm 字面信息。",
                        )
                    )
        return issues


class MainGoalProgressionEvaluator(_EvaluatorBase):
    issue_type = "main_goal_progression"

    def evaluate(self, context: BookContinuityCheckInput) -> list[ConsistencyIssue]:
        issues: list[ConsistencyIssue] = []
        if not context.finalized_volumes:
            return issues

        main_tokens = self._tokenize(
            " ".join(
                [
                    context.story_bible.story_promise,
                    *context.story_bible.core_conflicts,
                ]
            )
        )
        if not main_tokens:
            return issues

        detached_flags: list[bool] = []
        for entry in context.finalized_volumes:
            volume_tokens = self._tokenize(
                " ".join(
                    [
                        entry.volume.goal,
                        entry.volume.core_conflict,
                        entry.artifact.summary,
                        entry.artifact.hook,
                    ]
                )
            )
            detached = not bool(main_tokens & volume_tokens)
            detached_flags.append(detached)
            if detached:
                issues.append(
                    self._issue(
                        context,
                        "continuity.goal.volume.detached",
                        "warning",
                        f"卷 {entry.volume.volume_no} 与主线目标关键词没有字面交集。",
                    )
                )

        if len(context.finalized_volumes) >= 2 and all(detached_flags[-2:]):
            issues.append(
                self._issue(
                    context,
                    "continuity.goal.last_two.detached",
                    "blocker",
                    "最后 2 个 finalized volumes 与主线目标关键词都没有字面交集。",
                )
            )
        return issues


class ThreadDriftEvaluator(_EvaluatorBase):
    issue_type = "thread_drift"

    def evaluate(self, context: BookContinuityCheckInput) -> list[ConsistencyIssue]:
        issues: list[ConsistencyIssue] = []
        finalized = context.finalized_volumes
        if len(finalized) < 3:
            return issues

        finalized_texts = [
            self._tokenize(f"{entry.artifact.summary} {entry.artifact.hook}") for entry in finalized
        ]
        for index, entry in enumerate(finalized[:-2]):
            hook = entry.artifact.hook.strip()
            if not hook:
                continue
            hook_tokens = self._tokenize(hook)
            if not hook_tokens:
                continue
            future_tokens = finalized_texts[index + 1] | finalized_texts[index + 2]
            if hook_tokens.isdisjoint(future_tokens):
                issues.append(
                    self._issue(
                        context,
                        "continuity.thread.drift",
                        "warning",
                        f"卷 {entry.volume.volume_no} 的长期 hook 在线程上出现漂移，之后连续 2 卷未再命中。",
                    )
                )
        return issues


class CrossVolumeProgressionEvaluator(_EvaluatorBase):
    issue_type = "cross_volume_progression"

    def evaluate(self, context: BookContinuityCheckInput) -> list[ConsistencyIssue]:
        issues: list[ConsistencyIssue] = []
        canonical_order = [volume.volume_id for volume in context.planned_volumes]
        if context.book_assembled.planned_volume_order != canonical_order:
            issues.append(
                self._issue(
                    context,
                    "continuity.progression.order.invalid",
                    "blocker",
                    "book assembled 的 planned_volume_order 与当前 canonical planned volumes 不一致。",
                )
            )

        artifact_versions = {entry.volume.volume_id: entry.artifact.version for entry in context.finalized_volumes}
        for item in context.book_assembled.volume_order:
            actual_version = artifact_versions.get(item.volume_id)
            if actual_version is None or actual_version != item.assembled_version:
                issues.append(
                    self._issue(
                        context,
                        "continuity.progression.version.mismatch",
                        "blocker",
                        f"卷 {item.volume_id} 的 assembled_version 与当前 finalized volume artifact 不一致。",
                    )
                )

        ratio = context.book_assembled.progress_stats.completion_ratio
        if ratio < 0.0 or ratio > 1.0:
            issues.append(
                self._issue(
                    context,
                    "continuity.progression.completion_ratio.invalid",
                    "blocker",
                    "book assembled.progress_stats.completion_ratio 不在 0.0~1.0 范围内。",
                )
            )

        volume_nos = [item.volume_no for item in context.book_assembled.volume_order]
        if len(volume_nos) >= 2:
            sorted_nos = sorted(volume_nos)
            if any(current - previous > 1 for previous, current in zip(sorted_nos, sorted_nos[1:])):
                issues.append(
                    self._issue(
                        context,
                        "continuity.progression.gap",
                        "warning",
                        "finalized volume progression 存在 gap（例如 1,3）。",
                    )
                )
        return issues
