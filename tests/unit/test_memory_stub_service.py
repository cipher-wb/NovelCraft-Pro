from __future__ import annotations


def test_memory_stub_upserts_by_scene_and_sorts_stably(service_container) -> None:
    from backend.app.domain.models.planning import ScenePlan
    from backend.app.domain.models.writing import SceneDraft
    from backend.app.services.memory_stub_service import MemoryStubService

    container = service_container
    seeded = container["seed_project"](ready_scene=True, scene_count_hint=2)
    manifest = seeded["manifest"]
    paths = seeded["paths"]
    file_repository = seeded["file_repository"]

    service = MemoryStubService(paths, file_repository)
    second_scene = seeded["scenes"][1]

    draft_b = SceneDraft.model_validate(
        {
            "draft_id": "draft_b",
            "project_id": manifest.project_id,
            "volume_id": seeded["volume_id"],
            "chapter_id": seeded["chapter_id"],
            "scene_id": second_scene.scene_id,
            "chapter_no": 1,
            "scene_no": 2,
            "draft_no": 2,
            "operation": "generate",
            "candidate_mode": "outline_strict",
            "status": "accepted",
            "content_md": "第二场正文",
            "summary": "第二场摘要",
            "context_bundle_id": "ctx_b",
            "context_bundle_path": "drafts/scenes/scene_0001_002/context-bundle-002.json",
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
    scene_b = ScenePlan.model_validate(
        {
            "scene_id": second_scene.scene_id,
            "project_id": manifest.project_id,
            "volume_id": seeded["volume_id"],
            "chapter_id": seeded["chapter_id"],
            "chapter_no": 1,
            "scene_no": 2,
            "title": "第二场",
            "summary": "第二场计划摘要",
            "scene_type": "pressure",
            "goal": "推进",
            "obstacle": "阻碍",
            "turning_point": "转折",
            "outcome": "结果",
            "location_id": None,
            "time_anchor": "",
            "character_ids": [],
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

    draft_a = draft_b.model_copy(update={
        "draft_id": "draft_a",
        "scene_id": seeded["scene_id"],
        "scene_no": 1,
        "draft_no": 1,
        "summary": "第一场摘要",
        "context_bundle_id": "ctx_a",
        "context_bundle_path": "drafts/scenes/scene_0001_001/context-bundle-001.json",
    })
    scene_a = scene_b.model_copy(update={
        "scene_id": seeded["scene_id"],
        "scene_no": 1,
        "title": "第一场",
        "summary": "第一场计划摘要",
    })

    service.ingest_accepted_scene(manifest.slug, draft_b, scene_b)
    service.ingest_accepted_scene(manifest.slug, draft_a, scene_a)
    service.ingest_accepted_scene(manifest.slug, draft_a.model_copy(update={"summary": "第一场新摘要", "draft_id": "draft_a2"}), scene_a)

    payload = file_repository.read_json(paths.accepted_scenes_memory_path(manifest.slug))
    items = payload["items"]
    assert [item["scene_no"] for item in items] == [1, 2]
    assert items[0]["draft_id"] == "draft_a2"
    assert items[0]["summary"] == "第一场新摘要"
    assert len([item for item in items if item["scene_id"] == seeded["scene_id"]]) == 1
