from __future__ import annotations

from pathlib import Path


def test_context_bundle_compacts_allowed_fields_and_reads_previous_accepted_summary(service_container) -> None:
    container = service_container
    seeded = container["seed_project"](ready_scene=True, scene_count_hint=2)

    from backend.app.domain.models.writing import AcceptedSceneMemoryDocument, AcceptedSceneMemoryItem
    from backend.app.services.context_bundle_service import ContextBundleService

    manifest = seeded["manifest"]
    paths = seeded["paths"]
    file_repository = seeded["file_repository"]
    planner_service = seeded["planner_service"]
    bible_service = seeded["bible_service"]

    second_scene = seeded["scenes"][1]
    planner_service.confirm_scene(manifest.project_id, second_scene.scene_id)

    accepted_doc = AcceptedSceneMemoryDocument(
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
                scene_title="前一场",
                scene_type="setup",
                summary="前一场 accepted 摘要",
                summary_source="draft_summary",
                character_ids=[],
                location_id=None,
                time_anchor="",
                accepted_at="2026-03-12T00:00:00Z",
                source_scene_version=1,
            )
        ],
        updated_at="2026-03-12T00:00:00Z",
    )
    file_repository.write_json(paths.accepted_scenes_memory_path(manifest.slug), accepted_doc.model_dump(mode="json"))

    service = ContextBundleService(paths, file_repository, bible_service, planner_service)
    bundle = service.build(manifest.project_id, second_scene.scene_id)

    payload = bundle.model_dump(mode="python")
    assert bundle.story_anchor.story_promise
    assert bundle.chapter_anchor.chapter_id == seeded["chapter_id"]
    assert bundle.scene_anchor.scene_id == second_scene.scene_id
    assert bundle.continuity.previous_accepted_scene_summary == "前一场 accepted 摘要"
    assert "world_rules" not in payload
    assert "realm_ladder" not in payload
    assert "items" not in payload
