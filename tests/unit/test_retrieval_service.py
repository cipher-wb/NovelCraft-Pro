from __future__ import annotations


def test_retrieval_service_dedupes_recent_summaries_and_character_states(service_container) -> None:
    from backend.app.domain.models.writing import (
        AcceptedSceneMemoryDocument,
        AcceptedSceneMemoryItem,
        CharacterStateSummariesMemoryDocument,
        CharacterStateSummaryMemoryItem,
        ChapterSummariesMemoryDocument,
    )
    from backend.app.services.retrieval_service import RetrievalService

    container = service_container
    seeded = container["seed_project"](ready_scene=True, scene_count_hint=3)
    manifest = seeded["manifest"]
    paths = seeded["paths"]
    file_repository = seeded["file_repository"]
    sqlite_repository = seeded["sqlite_repository"]
    planner_service = seeded["planner_service"]

    target_scene = seeded["scenes"][2]
    planner_service.update_scene(manifest.project_id, target_scene.scene_id, {"character_ids": ["char_mc"]})

    file_repository.write_json(
        paths.accepted_scenes_memory_path(manifest.slug),
        AcceptedSceneMemoryDocument(
            project_id=manifest.project_id,
            items=[
                AcceptedSceneMemoryItem(
                    memory_id="mem_1",
                    scene_id=seeded["scene_id"],
                    chapter_id=seeded["chapter_id"],
                    volume_id=seeded["volume_id"],
                    draft_id="draft_1",
                    chapter_no=1,
                    scene_no=1,
                    volume_no=1,
                    chapter_title="第1章",
                    scene_title="第一场",
                    scene_type="setup",
                    summary="第一场摘要",
                    summary_source="draft_summary",
                    scene_goal="第一场目标",
                    scene_outcome="第一场结果",
                    character_ids=["char_mc"],
                    faction_ids=[],
                    location_id=None,
                    time_anchor="",
                    accepted_at="2026-03-12T00:00:00Z",
                    source_scene_version=1,
                ),
                AcceptedSceneMemoryItem(
                    memory_id="mem_2_old",
                    scene_id=seeded["scenes"][1].scene_id,
                    chapter_id=seeded["chapter_id"],
                    volume_id=seeded["volume_id"],
                    draft_id="draft_2a",
                    chapter_no=1,
                    scene_no=2,
                    volume_no=1,
                    chapter_title="第1章",
                    scene_title="第二场",
                    scene_type="pressure",
                    summary="第二场旧摘要",
                    summary_source="draft_summary",
                    scene_goal="第二场目标",
                    scene_outcome="第二场旧结果",
                    character_ids=["char_mc"],
                    faction_ids=[],
                    location_id=None,
                    time_anchor="",
                    accepted_at="2026-03-12T00:01:00Z",
                    source_scene_version=1,
                ),
                AcceptedSceneMemoryItem(
                    memory_id="mem_2_new",
                    scene_id=seeded["scenes"][1].scene_id,
                    chapter_id=seeded["chapter_id"],
                    volume_id=seeded["volume_id"],
                    draft_id="draft_2b",
                    chapter_no=1,
                    scene_no=2,
                    volume_no=1,
                    chapter_title="第1章",
                    scene_title="第二场",
                    scene_type="pressure",
                    summary="第二场新摘要",
                    summary_source="draft_summary",
                    scene_goal="第二场目标",
                    scene_outcome="第二场新结果",
                    character_ids=["char_mc"],
                    faction_ids=[],
                    location_id=None,
                    time_anchor="",
                    accepted_at="2026-03-12T00:02:00Z",
                    source_scene_version=1,
                ),
            ],
            updated_at="2026-03-12T00:02:00Z",
        ).model_dump(mode="json"),
    )
    file_repository.write_json(
        paths.chapter_summaries_memory_path(manifest.slug),
        ChapterSummariesMemoryDocument(project_id=manifest.project_id, updated_at="2026-03-12T00:00:00Z").model_dump(mode="json"),
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
                    latest_scene_summary="第一场摘要",
                    last_scene_goal="第一场目标",
                    last_scene_outcome="第一场结果",
                    related_character_ids=[],
                    source_draft_id="draft_1",
                    updated_at="2026-03-12T00:00:00Z",
                ),
                CharacterStateSummaryMemoryItem(
                    character_id="char_mc",
                    character_name="主角",
                    last_scene_id=seeded["scenes"][1].scene_id,
                    last_chapter_id=seeded["chapter_id"],
                    last_volume_id=seeded["volume_id"],
                    last_chapter_no=1,
                    last_scene_no=2,
                    latest_location_id=None,
                    latest_time_anchor="",
                    latest_scene_summary="第二场新摘要",
                    last_scene_goal="第二场目标",
                    last_scene_outcome="第二场新结果",
                    related_character_ids=[],
                    source_draft_id="draft_2b",
                    updated_at="2026-03-12T00:02:00Z",
                ),
            ],
            updated_at="2026-03-12T00:02:00Z",
        ).model_dump(mode="json"),
    )

    service = RetrievalService(paths, file_repository, sqlite_repository, planner_service)
    retrieved = service.retrieve_for_scene(manifest.project_id, target_scene.scene_id)

    assert [item.scene_id for item in retrieved.recent_scene_summaries] == [seeded["scenes"][1].scene_id, seeded["scene_id"]]
    assert len(retrieved.character_state_briefs) == 1
    assert retrieved.character_state_briefs[0].last_scene_no == 2


def test_retrieval_service_degrades_gracefully_when_memory_documents_are_missing_or_invalid(service_container) -> None:
    from backend.app.services.retrieval_service import RetrievalService

    container = service_container
    seeded = container["seed_project"](ready_scene=True, scene_count_hint=1)
    manifest = seeded["manifest"]
    paths = seeded["paths"]
    file_repository = seeded["file_repository"]
    sqlite_repository = seeded["sqlite_repository"]
    planner_service = seeded["planner_service"]

    file_repository.write_text(paths.chapter_summaries_memory_path(manifest.slug), "not-json")

    service = RetrievalService(paths, file_repository, sqlite_repository, planner_service)
    retrieved = service.retrieve_for_scene(manifest.project_id, seeded["scene_id"])

    assert retrieved.recent_scene_summaries == []
    assert retrieved.character_state_briefs == []
    assert retrieved.previous_chapter_summary is None
    assert retrieved.warnings
