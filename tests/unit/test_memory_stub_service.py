from __future__ import annotations


def test_memory_service_ingest_updates_all_memory_documents(service_container) -> None:
    from backend.app.domain.models.planning import ScenePlan
    from backend.app.domain.models.writing import SceneDraft
    from backend.app.services.memory_service import MemoryService

    container = service_container
    seeded = container["seed_project"](ready_scene=True, scene_count_hint=2)
    manifest = seeded["manifest"]
    paths = seeded["paths"]
    file_repository = seeded["file_repository"]
    bible_service = seeded["bible_service"]
    planner_service = seeded["planner_service"]

    service = MemoryService(paths, file_repository, bible_service)
    chapter = planner_service.get_chapter(manifest.project_id, seeded["chapter_id"])
    volume = planner_service.get_volume(manifest.project_id, seeded["volume_id"])
    scene = planner_service.get_scene(manifest.project_id, seeded["scene_id"]).model_copy(
        update={
            "character_ids": ["char_mc"],
            "location_id": "loc_home",
            "goal": "觉醒",
            "outcome": "完成觉醒",
        }
    )
    draft = SceneDraft.model_validate(
        {
            "draft_id": "draft_a",
            "project_id": manifest.project_id,
            "volume_id": seeded["volume_id"],
            "chapter_id": seeded["chapter_id"],
            "scene_id": seeded["scene_id"],
            "chapter_no": 1,
            "scene_no": 1,
            "draft_no": 1,
            "operation": "generate",
            "candidate_mode": "outline_strict",
            "status": "accepted",
            "content_md": "第一场正文",
            "summary": "第一场摘要",
            "context_bundle_id": "ctx_a",
            "context_bundle_path": "drafts/scenes/scene_0001_001/context-bundle-001.json",
            "model_name": "mock",
            "tokens_in": 0,
            "tokens_out": 0,
            "source_scene_version": 1,
            "source_chapter_version": 1,
            "source_volume_version": 1,
            "created_at": "2026-03-12T00:00:00Z",
            "updated_at": "2026-03-12T00:00:00Z",
            "accepted_at": "2026-03-12T00:00:00Z",
            "rejected_at": None,
            "supersedes_draft_id": None,
            "memory_stub_record_id": None,
        }
    )

    result = service.ingest_accepted_draft(manifest.slug, draft, scene, chapter, volume)

    accepted_payload = file_repository.read_json(paths.accepted_scenes_memory_path(manifest.slug))
    chapter_payload = file_repository.read_json(paths.chapter_summaries_memory_path(manifest.slug))
    character_payload = file_repository.read_json(paths.character_state_summaries_memory_path(manifest.slug))

    assert result.accepted_scene_item.memory_id
    assert accepted_payload["items"][0]["scene_goal"] == "觉醒"
    assert accepted_payload["items"][0]["scene_outcome"] == "完成觉醒"
    assert accepted_payload["items"][0]["chapter_title"] == chapter.title
    assert chapter_payload["items"][0]["summary_source"] == "accepted_scene_rollup"
    assert chapter_payload["items"][0]["key_turns"] == [f"{scene.title}：觉醒 -> 完成觉醒"]
    assert character_payload["items"][0]["character_id"] == "char_mc"
    assert character_payload["items"][0]["last_scene_goal"] == "觉醒"
    assert character_payload["items"][0]["last_scene_outcome"] == "完成觉醒"


def test_memory_service_keeps_latest_character_state_and_scene_upsert(service_container) -> None:
    from backend.app.domain.models.planning import ChapterPlan, ScenePlan, VolumePlan
    from backend.app.domain.models.writing import SceneDraft
    from backend.app.services.memory_service import MemoryService

    container = service_container
    seeded = container["seed_project"](ready_scene=True, scene_count_hint=2)
    manifest = seeded["manifest"]
    paths = seeded["paths"]
    file_repository = seeded["file_repository"]
    bible_service = seeded["bible_service"]
    planner_service = seeded["planner_service"]

    service = MemoryService(paths, file_repository, bible_service)
    volume = planner_service.get_volume(manifest.project_id, seeded["volume_id"])
    chapter_one = planner_service.get_chapter(manifest.project_id, seeded["chapter_id"])
    scene_one = planner_service.get_scene(manifest.project_id, seeded["scene_id"]).model_copy(
        update={"character_ids": ["char_mc"], "goal": "开局受压", "outcome": "决定反击"}
    )
    draft_one = SceneDraft.model_validate(
        {
            "draft_id": "draft_one",
            "project_id": manifest.project_id,
            "volume_id": seeded["volume_id"],
            "chapter_id": seeded["chapter_id"],
            "scene_id": seeded["scene_id"],
            "chapter_no": 1,
            "scene_no": 1,
            "draft_no": 1,
            "operation": "generate",
            "candidate_mode": "outline_strict",
            "status": "accepted",
            "content_md": "第一场正文",
            "summary": "第一场摘要",
            "context_bundle_id": "ctx_one",
            "context_bundle_path": "drafts/scenes/scene_0001_001/context-bundle-001.json",
            "model_name": "mock",
            "tokens_in": 0,
            "tokens_out": 0,
            "source_scene_version": 1,
            "source_chapter_version": 1,
            "source_volume_version": 1,
            "created_at": "2026-03-12T00:00:00Z",
            "updated_at": "2026-03-12T00:00:00Z",
            "accepted_at": "2026-03-12T00:00:00Z",
            "rejected_at": None,
            "supersedes_draft_id": None,
            "memory_stub_record_id": None,
        }
    )
    service.ingest_accepted_draft(manifest.slug, draft_one, scene_one, chapter_one, volume)
    service.ingest_accepted_draft(
        manifest.slug,
        draft_one.model_copy(update={"draft_id": "draft_one_b", "summary": "第一场新摘要", "accepted_at": "2026-03-12T00:01:00Z"}),
        scene_one,
        chapter_one,
        volume,
    )

    chapter_two = ChapterPlan.model_validate(
        {
            "chapter_id": "chapter_0002",
            "project_id": manifest.project_id,
            "volume_id": seeded["volume_id"],
            "volume_no": 1,
            "chapter_no": 2,
            "title": "第二章",
            "summary": "第二章摘要",
            "purpose": "推进",
            "main_conflict": "冲突",
            "hook": "钩子",
            "entry_state": [],
            "exit_state": [],
            "character_ids": ["char_mc"],
            "faction_ids": [],
            "foreshadow_ids": [],
            "payoff_ids": [],
            "target_words": 3000,
            "scene_ids": ["scene_0002_001"],
            "source_volume_version": 1,
            "status": "ready",
            "version": 1,
            "stale_reason": None,
        }
    )
    scene_two = ScenePlan.model_validate(
        {
            "scene_id": "scene_0002_001",
            "project_id": manifest.project_id,
            "volume_id": seeded["volume_id"],
            "chapter_id": "chapter_0002",
            "chapter_no": 2,
            "scene_no": 1,
            "title": "第二章第一场",
            "summary": "第二场计划摘要",
            "scene_type": "turn",
            "goal": "主动出击",
            "obstacle": "对手压制",
            "turning_point": "抓住破绽",
            "outcome": "立住气势",
            "location_id": None,
            "time_anchor": "",
            "character_ids": ["char_mc"],
            "must_include": [],
            "forbidden": [],
            "target_words": 1200,
            "emotional_beat": "",
            "continuity_notes": "",
            "source_chapter_version": 1,
            "status": "ready",
            "version": 1,
            "stale_reason": None,
        }
    )
    draft_two = draft_one.model_copy(
        update={
            "draft_id": "draft_two",
            "chapter_id": "chapter_0002",
            "scene_id": "scene_0002_001",
            "chapter_no": 2,
            "scene_no": 1,
            "draft_no": 2,
            "summary": "第二场摘要",
            "accepted_at": "2026-03-12T00:02:00Z",
        }
    )
    service.ingest_accepted_draft(manifest.slug, draft_two, scene_two, chapter_two, VolumePlan.model_validate(volume.model_dump(mode="python")))

    accepted_payload = file_repository.read_json(paths.accepted_scenes_memory_path(manifest.slug))
    character_payload = file_repository.read_json(paths.character_state_summaries_memory_path(manifest.slug))

    assert len([item for item in accepted_payload["items"] if item["scene_id"] == seeded["scene_id"]]) == 1
    assert accepted_payload["items"][0]["draft_id"] == "draft_one_b"
    assert character_payload["items"][0]["source_draft_id"] == "draft_two"
    assert character_payload["items"][0]["last_chapter_no"] == 2
