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


def test_retrieval_service_injects_previous_volume_summary_only_for_first_two_canonical_planned_chapters(service_container) -> None:
    from backend.app.domain.models.writing import VolumeSummariesMemoryDocument
    from backend.app.schemas.project import CreateProjectRequest
    from backend.app.services.retrieval_service import RetrievalService

    container = service_container
    manifest, _ = container["project_service"].create_project(
        CreateProjectRequest(
            title="跨卷检索测试书",
            genre="都市异能",
            target_chapters=6,
            target_words=600_000,
        )
    )
    paths = container["paths"]
    file_repository = container["file_repository"]
    planner_service = container["planner_service"]
    bible_service = container["bible_service"]
    sqlite_repository = container["sqlite_repository"]

    file_repository.write_json(
        paths.consultant_dossier_path(manifest.slug),
        {
            "dossier_id": "dossier_cross_volume",
            "project_id": manifest.project_id,
            "high_concept": "跨卷推进测试",
            "subgenres": ["升级流"],
            "target_audience": ["男频爽文读者"],
            "selling_points": ["升级", "打脸"],
            "protagonist_seed": {"summary": "主角"},
            "golden_finger": {"summary": "系统"},
            "core_conflicts": ["势力冲突"],
            "chapter_1_30_beats": [{"range": "1-10", "focus": "开局"}],
            "qa_transcript": [],
            "version": 1,
        },
    )

    bible_service.initialize_from_consultant(manifest.project_id)
    bible_service.confirm_characters(manifest.project_id)
    bible_service.confirm_world(manifest.project_id)
    bible_service.confirm_power_system(manifest.project_id)
    bible_service.confirm_story_bible(manifest.project_id)

    outline = planner_service.generate_volumes(manifest.project_id, volume_count_hint=2, chapters_per_volume_hint=3)
    volume_one_id = outline.volumes[0].volume_id
    volume_two_id = outline.volumes[1].volume_id
    planner_service.confirm_master_outline(manifest.project_id)
    planner_service.confirm_volume(manifest.project_id, volume_one_id)
    planner_service.confirm_volume(manifest.project_id, volume_two_id)

    planner_service.generate_chapters(manifest.project_id, volume_one_id)
    chapters_two = planner_service.generate_chapters(manifest.project_id, volume_two_id)
    scenes = []
    for chapter in chapters_two:
        planner_service.confirm_chapter(manifest.project_id, chapter.chapter_id)
        generated_scene = planner_service.generate_scenes(manifest.project_id, chapter.chapter_id, scene_count_hint=1)[0]
        planner_service.confirm_scene(manifest.project_id, generated_scene.scene_id)
        scenes.append(generated_scene)

    file_repository.write_json(
        paths.volume_summaries_memory_path(manifest.slug),
        VolumeSummariesMemoryDocument(
            project_id=manifest.project_id,
            items=[
                {
                    "volume_id": volume_one_id,
                    "volume_no": 1,
                    "title": "第一卷",
                    "summary": "上一卷摘要",
                    "hook": "上一卷钩子",
                    "planned_chapter_count": 3,
                    "finalized_chapter_count": 3,
                    "finalized_chapter_ids": ["chapter_0001", "chapter_0002", "chapter_0003"],
                    "updated_at": "2026-03-13T00:00:00Z",
                }
            ],
            updated_at="2026-03-13T00:00:00Z",
        ).model_dump(mode="json"),
    )

    service = RetrievalService(paths, file_repository, sqlite_repository, planner_service)
    first = service.retrieve_for_scene(manifest.project_id, scenes[0].scene_id)
    second = service.retrieve_for_scene(manifest.project_id, scenes[1].scene_id)
    third = service.retrieve_for_scene(manifest.project_id, scenes[2].scene_id)

    assert first.previous_volume_summary is not None
    assert first.previous_volume_summary.selection_reason == "volume_boundary"
    assert second.previous_volume_summary is not None
    assert second.previous_volume_summary.selection_reason == "early_volume_context"
    assert third.previous_volume_summary is None


def test_retrieval_service_warns_on_duplicate_previous_volume_summaries_and_picks_latest(service_container) -> None:
    from backend.app.domain.models.writing import VolumeSummariesMemoryDocument
    from backend.app.schemas.project import CreateProjectRequest
    from backend.app.services.retrieval_service import RetrievalService

    container = service_container
    manifest, _ = container["project_service"].create_project(
        CreateProjectRequest(
            title="跨卷重复摘要测试书",
            genre="都市异能",
            target_chapters=4,
            target_words=400_000,
        )
    )
    paths = container["paths"]
    file_repository = container["file_repository"]
    planner_service = container["planner_service"]
    bible_service = container["bible_service"]
    sqlite_repository = container["sqlite_repository"]

    file_repository.write_json(
        paths.consultant_dossier_path(manifest.slug),
        {
            "dossier_id": "dossier_duplicate_volume",
            "project_id": manifest.project_id,
            "high_concept": "跨卷重复候选测试",
            "subgenres": ["升级流"],
            "target_audience": ["男频爽文读者"],
            "selling_points": ["升级"],
            "protagonist_seed": {"summary": "主角"},
            "golden_finger": {"summary": "系统"},
            "core_conflicts": ["势力冲突"],
            "chapter_1_30_beats": [{"range": "1-10", "focus": "开局"}],
            "qa_transcript": [],
            "version": 1,
        },
    )

    bible_service.initialize_from_consultant(manifest.project_id)
    bible_service.confirm_characters(manifest.project_id)
    bible_service.confirm_world(manifest.project_id)
    bible_service.confirm_power_system(manifest.project_id)
    bible_service.confirm_story_bible(manifest.project_id)

    outline = planner_service.generate_volumes(manifest.project_id, volume_count_hint=2, chapters_per_volume_hint=2)
    volume_two_id = outline.volumes[1].volume_id
    planner_service.confirm_master_outline(manifest.project_id)


def test_retrieval_service_injects_book_summary_only_for_last_two_canonical_planned_volumes(service_container) -> None:
    from backend.app.domain.models.writing import BookSummaryMemoryDocument
    from backend.app.schemas.project import CreateProjectRequest
    from backend.app.services.retrieval_service import RetrievalService

    container = service_container
    manifest, _ = container["project_service"].create_project(
        CreateProjectRequest(
            title="整书摘要注入测试书",
            genre="都市异能",
            target_chapters=9,
            target_words=900_000,
        )
    )
    paths = container["paths"]
    file_repository = container["file_repository"]
    planner_service = container["planner_service"]
    bible_service = container["bible_service"]
    sqlite_repository = container["sqlite_repository"]

    file_repository.write_json(
        paths.consultant_dossier_path(manifest.slug),
        {
            "dossier_id": "dossier_book_summary",
            "project_id": manifest.project_id,
            "high_concept": "整书摘要注入测试",
            "subgenres": ["升级流"],
            "target_audience": ["男频爽文读者"],
            "selling_points": ["升级"],
            "protagonist_seed": {"summary": "主角"},
            "golden_finger": {"summary": "系统"},
            "core_conflicts": ["势力冲突"],
            "chapter_1_30_beats": [{"range": "1-10", "focus": "开局"}],
            "qa_transcript": [],
            "version": 1,
        },
    )

    bible_service.initialize_from_consultant(manifest.project_id)
    bible_service.confirm_characters(manifest.project_id)
    bible_service.confirm_world(manifest.project_id)
    bible_service.confirm_power_system(manifest.project_id)
    bible_service.confirm_story_bible(manifest.project_id)

    outline = planner_service.generate_volumes(manifest.project_id, volume_count_hint=3, chapters_per_volume_hint=1)
    planner_service.confirm_master_outline(manifest.project_id)
    scene_ids_by_volume: dict[str, str] = {}
    volume_ids = [item.volume_id for item in outline.volumes]
    for volume_id in volume_ids:
        planner_service.confirm_volume(manifest.project_id, volume_id)
        chapter = planner_service.generate_chapters(manifest.project_id, volume_id)[0]
        planner_service.confirm_chapter(manifest.project_id, chapter.chapter_id)
        scene = planner_service.generate_scenes(manifest.project_id, chapter.chapter_id, scene_count_hint=1)[0]
        planner_service.confirm_scene(manifest.project_id, scene.scene_id)
        scene_ids_by_volume[volume_id] = scene.scene_id

    file_repository.write_json(
        paths.book_summary_memory_path(manifest.slug),
        BookSummaryMemoryDocument(
            project_id=manifest.project_id,
            version=1,
            updated_at="2026-03-13T00:00:00Z",
            summary="整书摘要",
            hook="整书钩子",
            planned_volume_count=3,
            finalized_volume_count=3,
            finalized_volume_ids=volume_ids,
        ).model_dump(mode="json"),
    )

    service = RetrievalService(paths, file_repository, sqlite_repository, planner_service)
    first = service.retrieve_for_scene(manifest.project_id, scene_ids_by_volume[volume_ids[0]])
    second = service.retrieve_for_scene(manifest.project_id, scene_ids_by_volume[volume_ids[1]])
    third = service.retrieve_for_scene(manifest.project_id, scene_ids_by_volume[volume_ids[2]])

    assert first.book_summary is None
    assert second.book_summary is not None
    assert second.book_summary.summary == "整书摘要"
    assert third.book_summary is not None
    assert third.book_summary.hook == "整书钩子"


def test_retrieval_service_degrades_gracefully_when_book_summary_is_missing_or_invalid(service_container) -> None:
    from backend.app.schemas.project import CreateProjectRequest
    from backend.app.services.retrieval_service import RetrievalService

    container = service_container
    manifest, _ = container["project_service"].create_project(
        CreateProjectRequest(
            title="整书摘要降级测试书",
            genre="都市异能",
            target_chapters=6,
            target_words=600_000,
        )
    )
    paths = container["paths"]
    file_repository = container["file_repository"]
    planner_service = container["planner_service"]
    bible_service = container["bible_service"]
    sqlite_repository = container["sqlite_repository"]

    file_repository.write_json(
        paths.consultant_dossier_path(manifest.slug),
        {
            "dossier_id": "dossier_book_summary_fallback",
            "project_id": manifest.project_id,
            "high_concept": "整书摘要降级测试",
            "subgenres": ["升级流"],
            "target_audience": ["男频爽文读者"],
            "selling_points": ["升级"],
            "protagonist_seed": {"summary": "主角"},
            "golden_finger": {"summary": "系统"},
            "core_conflicts": ["势力冲突"],
            "chapter_1_30_beats": [{"range": "1-10", "focus": "开局"}],
            "qa_transcript": [],
            "version": 1,
        },
    )

    bible_service.initialize_from_consultant(manifest.project_id)
    bible_service.confirm_characters(manifest.project_id)
    bible_service.confirm_world(manifest.project_id)
    bible_service.confirm_power_system(manifest.project_id)
    bible_service.confirm_story_bible(manifest.project_id)

    outline = planner_service.generate_volumes(manifest.project_id, volume_count_hint=2, chapters_per_volume_hint=1)
    planner_service.confirm_master_outline(manifest.project_id)
    target_volume_id = outline.volumes[1].volume_id
    for volume_id in [item.volume_id for item in outline.volumes]:
        planner_service.confirm_volume(manifest.project_id, volume_id)
        chapter = planner_service.generate_chapters(manifest.project_id, volume_id)[0]
        planner_service.confirm_chapter(manifest.project_id, chapter.chapter_id)
        scene = planner_service.generate_scenes(manifest.project_id, chapter.chapter_id, scene_count_hint=1)[0]
        planner_service.confirm_scene(manifest.project_id, scene.scene_id)
        if volume_id == target_volume_id:
            target_scene_id = scene.scene_id

    service = RetrievalService(paths, file_repository, sqlite_repository, planner_service)
    paths.book_summary_memory_path(manifest.slug).unlink()
    missing = service.retrieve_for_scene(manifest.project_id, target_scene_id)
    assert missing.book_summary is None
    assert RetrievalService.WARNING_BOOK_SUMMARY_UNAVAILABLE in missing.warnings

    file_repository.write_text(paths.book_summary_memory_path(manifest.slug), "{broken json")
    broken = service.retrieve_for_scene(manifest.project_id, target_scene_id)
    assert broken.book_summary is None
    assert RetrievalService.WARNING_BOOK_SUMMARY_UNAVAILABLE in broken.warnings
