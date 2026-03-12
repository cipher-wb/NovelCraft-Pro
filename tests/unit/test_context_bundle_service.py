from __future__ import annotations


def test_context_bundle_includes_retrieved_memory_and_keeps_compact_shape(service_container) -> None:
    container = service_container
    seeded = container["seed_project"](ready_scene=True, scene_count_hint=2)

    from backend.app.domain.models.planning import ScenePlan
    from backend.app.domain.models.writing import (
        AcceptedSceneMemoryDocument,
        AcceptedSceneMemoryItem,
        ChapterSummariesMemoryDocument,
        ChapterSummaryMemoryItem,
        CharacterStateSummariesMemoryDocument,
        CharacterStateSummaryMemoryItem,
    )
    from backend.app.services.context_bundle_service import ContextBundleService
    from backend.app.services.retrieval_service import RetrievalService

    manifest = seeded["manifest"]
    paths = seeded["paths"]
    file_repository = seeded["file_repository"]
    planner_service = seeded["planner_service"]
    bible_service = seeded["bible_service"]
    sqlite_repository = seeded["sqlite_repository"]

    second_scene = seeded["scenes"][1]
    planner_service.confirm_scene(manifest.project_id, second_scene.scene_id)
    planner_service.update_scene(manifest.project_id, second_scene.scene_id, {"character_ids": ["char_mc"]})

    file_repository.write_json(
        paths.accepted_scenes_memory_path(manifest.slug),
        AcceptedSceneMemoryDocument(
            project_id=manifest.project_id,
            items=[
                AcceptedSceneMemoryItem(
                    memory_id="mem_prev",
                    scene_id=seeded["scene_id"],
                    chapter_id=seeded["chapter_id"],
                    volume_id=seeded["volume_id"],
                    draft_id="draft_prev",
                    chapter_no=1,
                    scene_no=1,
                    volume_no=1,
                    chapter_title="第1章",
                    scene_title="前一场",
                    scene_type="setup",
                    summary="前一场 accepted 摘要",
                    summary_source="draft_summary",
                    scene_goal="前一场目标",
                    scene_outcome="前一场结果",
                    character_ids=["char_mc"],
                    faction_ids=[],
                    location_id=None,
                    time_anchor="",
                    accepted_at="2026-03-12T00:00:00Z",
                    source_scene_version=1,
                )
            ],
            updated_at="2026-03-12T00:00:00Z",
        ).model_dump(mode="json"),
    )
    file_repository.write_json(
        paths.chapter_summaries_memory_path(manifest.slug),
        ChapterSummariesMemoryDocument(
            project_id=manifest.project_id,
            items=[
                ChapterSummaryMemoryItem(
                    chapter_id=seeded["chapter_id"],
                    volume_id=seeded["volume_id"],
                    chapter_no=1,
                    chapter_title="第1章",
                    accepted_scene_ids=[seeded["scene_id"]],
                    accepted_scene_count=1,
                    summary="章节摘要",
                    summary_source="accepted_scene_rollup",
                    key_turns=["前一场：前一场目标 -> 前一场结果"],
                    last_scene_id=seeded["scene_id"],
                    last_scene_no=1,
                    updated_from_draft_id="draft_prev",
                    updated_at="2026-03-12T00:00:00Z",
                )
            ],
            updated_at="2026-03-12T00:00:00Z",
        ).model_dump(mode="json"),
    )
    file_repository.write_json(
        paths.character_state_summaries_memory_path(manifest.slug),
        CharacterStateSummariesMemoryDocument(
            project_id=manifest.project_id,
            items=[
                CharacterStateSummaryMemoryItem(
                    character_id="char_mc",
                    character_name="主角",
                    last_scene_id=seeded["scene_id"],
                    last_chapter_id=seeded["chapter_id"],
                    last_volume_id=seeded["volume_id"],
                    last_chapter_no=1,
                    last_scene_no=1,
                    latest_location_id=None,
                    latest_time_anchor="",
                    latest_scene_summary="前一场 accepted 摘要",
                    last_scene_goal="前一场目标",
                    last_scene_outcome="前一场结果",
                    related_character_ids=[],
                    source_draft_id="draft_prev",
                    updated_at="2026-03-12T00:00:00Z",
                )
            ],
            updated_at="2026-03-12T00:00:00Z",
        ).model_dump(mode="json"),
    )

    retrieval_service = RetrievalService(paths, file_repository, sqlite_repository, planner_service)
    service = ContextBundleService(paths, file_repository, bible_service, planner_service, retrieval_service)
    bundle = service.build(manifest.project_id, second_scene.scene_id)

    payload = bundle.model_dump(mode="python")
    assert bundle.continuity.previous_accepted_scene_summary == "前一场 accepted 摘要"
    assert bundle.retrieved_memory.recent_scene_summaries[0].scene_id == seeded["scene_id"]
    assert bundle.retrieved_memory.character_state_briefs[0].character_id == "char_mc"
    assert "world_rules" not in payload
    assert "realm_ladder" not in payload
    assert "items" not in payload
