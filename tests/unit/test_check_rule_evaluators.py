from __future__ import annotations

from backend.app.domain.models.common import utc_now
from backend.app.domain.models.planning import ChapterPlan, ScenePlan, VolumePlan
from backend.app.domain.models.project import (
    CharacterCard,
    CharacterDocument,
    Location,
    PowerSystemDocument,
    RealmLevel,
    StoryBible,
    WorldDocument,
)
from backend.app.domain.models.writing import ContextBundle
from backend.app.services.check_rule_evaluators import (
    CharacterConsistencyEvaluator,
    CheckInputContext,
    SceneAlignmentEvaluator,
    StyleConstraintEvaluator,
    TimelineOrderEvaluator,
    WorldPowerConflictEvaluator,
)


def _build_input(
    *,
    content_md: str,
    scene: ScenePlan | None = None,
    characters: CharacterDocument | None = None,
    world: WorldDocument | None = None,
    power_system: PowerSystemDocument | None = None,
    bundle: ContextBundle | None = None,
) -> CheckInputContext:
    scene = scene or ScenePlan(
        scene_id="scene_001",
        project_id="proj_001",
        volume_id="volume_001",
        chapter_id="chapter_0001",
        chapter_no=1,
        scene_no=2,
        title="场景",
        goal="打脸反击",
        obstacle="反派阻拦",
        turning_point="系统觉醒",
        outcome="当众立威",
        must_include=["功德面板", "主角爆发"],
        forbidden=["反派.*落败"],
        location_id="loc_target",
        character_ids=["char_mc", "char_other"],
    )
    chapter = ChapterPlan(
        chapter_id="chapter_0001",
        project_id="proj_001",
        volume_id="volume_001",
        volume_no=1,
        chapter_no=1,
        title="第一章",
        character_ids=["char_mc", "char_other"],
        faction_ids=[],
    )
    volume = VolumePlan(
        volume_id="volume_001",
        project_id="proj_001",
        volume_no=1,
        title="第一卷",
    )
    story_bible = StoryBible(
        bible_id="bible_001",
        project_id="proj_001",
        title="书名",
        status="ready",
        updated_at=utc_now(),
    )
    characters = characters or CharacterDocument(
        project_id="proj_001",
        status="ready",
        updated_at=utc_now(),
        items=[
            CharacterCard(
                character_id="char_mc",
                project_id="proj_001",
                name="顾望安",
                aliases=["小顾"],
                role="protagonist",
                is_protagonist=True,
                realm_level="炼气",
            ),
            CharacterCard(
                character_id="char_other",
                project_id="proj_001",
                name="顾望平",
                aliases=["小顾"],
                role="support",
                is_protagonist=False,
                realm_level="炼气",
            ),
        ],
    )
    world = world or WorldDocument(
        project_id="proj_001",
        status="ready",
        updated_at=utc_now(),
        locations=[
            Location(location_id="loc_target", name="云海市"),
            Location(location_id="loc_other", name="青岚山"),
        ],
    )
    power_system = power_system or PowerSystemDocument(
        project_id="proj_001",
        status="ready",
        updated_at=utc_now(),
        realm_ladder=[
            RealmLevel(level_id="r1", name="炼气", order=1),
            RealmLevel(level_id="r2", name="筑基", order=2),
        ],
    )
    bundle = bundle or ContextBundle.model_validate(
        {
            "context_bundle_id": "ctx_001",
            "project_id": "proj_001",
            "volume_id": "volume_001",
            "chapter_id": "chapter_0001",
            "scene_id": "scene_001",
            "created_at": utc_now(),
            "source_versions": {
                "story_bible_version": 1,
                "characters_version": 1,
                "world_version": 1,
                "power_system_version": 1,
                "volume_version": 1,
                "chapter_version": 1,
                "scene_version": 1,
            },
            "story_anchor": {"title": "书名"},
            "volume_anchor": {"volume_id": "volume_001", "volume_no": 1},
            "chapter_anchor": {"chapter_id": "chapter_0001", "chapter_no": 2},
            "scene_anchor": {"scene_id": "scene_001", "scene_no": 2},
            "character_briefs": [],
            "faction_briefs": [],
            "location_brief": {"location_id": "loc_target", "name": "云海市"},
            "power_brief": {"system_name": "修仙体系"},
            "continuity": {},
            "style_constraints": {
                "enabled": False,
                "profile_name": "",
                "global_constraints": {
                    "sentence_rhythm": {"baseline": "", "soft_max_sentence_chars": 0, "burst_short_lines": False},
                    "paragraph_rhythm": {"preferred_min_sentences": 0, "preferred_max_sentences": 0, "soft_max_sentences": 0},
                    "banned_phrases": [],
                    "narrative_habits": {
                        "narration_person": "",
                        "exposition_density": "",
                        "inner_monologue_density": "",
                        "dialogue_tag_style": "",
                    },
                    "payoff_style": {
                        "intensity": "",
                        "prefer_action_before_reaction": False,
                        "prefer_concrete_gain": False,
                        "avoid_empty_hype": False,
                    },
                },
                "character_voice_briefs": [],
                "warnings": [],
            },
            "retrieved_memory": {
                "recent_scene_summaries": [{"scene_id": "scene_000", "chapter_id": "chapter_0001", "scene_no": 3}],
                "previous_chapter_summary": {"chapter_id": "chapter_prev", "chapter_no": 2},
                "character_state_briefs": [],
            },
        }
    )
    return CheckInputContext(
        project_id="proj_001",
        draft_id="draft_001",
        draft_text=content_md,
        draft_summary="",
        story_bible=story_bible,
        characters=characters,
        world=world,
        power_system=power_system,
        volume=volume,
        chapter=chapter,
        scene=scene,
        context_bundle=bundle,
    )



def test_scene_alignment_uses_literal_matching_only() -> None:
    issues = SceneAlignmentEvaluator().evaluate(
        _build_input(content_md="反击羞辱 系统觉醒 当众立威 功德面板 反派正式落败")
    )
    rule_ids = {issue.rule_id for issue in issues}
    assert "scene.goal.missing" in rule_ids
    assert "scene.must_include.missing" in rule_ids
    assert "scene.forbidden.hit" not in rule_ids



def test_character_consistency_ignores_ambiguous_aliases() -> None:
    issues = CharacterConsistencyEvaluator().evaluate(_build_input(content_md="小顾在云海市迟疑。"))
    rule_ids = [issue.rule_id for issue in issues]
    assert "character.protagonist.missing" in rule_ids
    assert "character.participant.missing" in rule_ids



def test_timeline_order_flags_invalid_retrieval_and_missing_time_anchor() -> None:
    scene = ScenePlan(
        scene_id="scene_001",
        project_id="proj_001",
        volume_id="volume_001",
        chapter_id="chapter_0001",
        chapter_no=1,
        scene_no=2,
        title="场景",
        time_anchor="次日清晨",
        character_ids=["char_mc"],
    )
    issues = TimelineOrderEvaluator().evaluate(_build_input(content_md="顾望安来到云海市。", scene=scene))
    rule_ids = {issue.rule_id for issue in issues}
    assert "timeline.recent_scene.order" in rule_ids
    assert "timeline.previous_chapter.order" in rule_ids
    assert "timeline.time_anchor.missing" in rule_ids



def test_world_power_conflict_uses_canonical_locations_only() -> None:
    issues = WorldPowerConflictEvaluator().evaluate(
        _build_input(content_md="顾望安来到云海城，随后闯入青岚山并尝试筑基。")
    )
    rule_ids = {issue.rule_id for issue in issues}
    assert "world.location.conflict" in rule_ids
    assert "power.realm.conflict" in rule_ids


def test_style_constraint_evaluator_emits_warning_only_for_banned_phrase_and_rhythm() -> None:
    bundle = ContextBundle.model_validate(
        {
            "context_bundle_id": "ctx_001",
            "project_id": "proj_001",
            "volume_id": "volume_001",
            "chapter_id": "chapter_0001",
            "scene_id": "scene_001",
            "created_at": utc_now(),
            "source_versions": {
                "story_bible_version": 1,
                "characters_version": 1,
                "world_version": 1,
                "power_system_version": 1,
                "volume_version": 1,
                "chapter_version": 1,
                "scene_version": 1,
            },
            "story_anchor": {"title": "书名"},
            "volume_anchor": {"volume_id": "volume_001", "volume_no": 1},
            "chapter_anchor": {"chapter_id": "chapter_0001", "chapter_no": 1},
            "scene_anchor": {"scene_id": "scene_001", "scene_no": 2},
            "character_briefs": [],
            "faction_briefs": [],
            "location_brief": {"location_id": "loc_target", "name": "云海市"},
            "power_brief": {"system_name": "修仙体系"},
            "continuity": {},
            "style_constraints": {
                "enabled": True,
                "profile_name": "风格",
                "global_constraints": {
                    "sentence_rhythm": {"baseline": "short", "soft_max_sentence_chars": 8, "burst_short_lines": True},
                    "paragraph_rhythm": {"preferred_min_sentences": 1, "preferred_max_sentences": 2, "soft_max_sentences": 1},
                    "banned_phrases": ["空气都安静了"],
                    "narrative_habits": {
                        "narration_person": "third_limited",
                        "exposition_density": "low",
                        "inner_monologue_density": "low",
                        "dialogue_tag_style": "simple",
                    },
                    "payoff_style": {
                        "intensity": "direct",
                        "prefer_action_before_reaction": True,
                        "prefer_concrete_gain": True,
                        "avoid_empty_hype": True,
                    },
                },
                "character_voice_briefs": [],
                "warnings": [],
            },
            "retrieved_memory": {"recent_scene_summaries": [], "character_state_briefs": []},
        }
    )
    issues = StyleConstraintEvaluator().evaluate(
        _build_input(
            content_md="空气都安静了。这个句子会非常非常长因为它完全没有收束。第二句。",
            bundle=bundle,
        )
    )
    rule_ids = {issue.rule_id for issue in issues}
    severities = {issue.severity for issue in issues}
    assert "style.banned_phrase.hit" in rule_ids
    assert "style.sentence.too_long" in rule_ids
    assert "style.paragraph.too_long" in rule_ids
    assert severities == {"warning"}
