from __future__ import annotations

import pytest


@pytest.mark.parametrize(
    ("target", "path_getter"),
    [
        ("story_bible", lambda paths, slug: paths.story_bible_path(slug)),
        ("characters", lambda paths, slug: paths.characters_path(slug)),
        ("world", lambda paths, slug: paths.world_path(slug)),
        ("power_system", lambda paths, slug: paths.power_system_path(slug)),
        ("volume", lambda paths, slug: paths.volume_plan_path(slug, 1)),
        ("chapter", lambda paths, slug: paths.chapter_plan_path(slug, 1)),
        ("scene", lambda paths, slug: paths.scene_plan_path(slug, 1, 1)),
    ],
)
def test_generate_requires_all_ready_documents(service_container, target: str, path_getter) -> None:
    from backend.app.services.context_bundle_service import ContextBundleService
    from backend.app.services.memory_stub_service import MemoryStubService
    from backend.app.services.scene_draft_service import SceneDraftService
    from backend.app.services.exceptions import ConflictError

    container = service_container
    seeded = container["seed_project"](ready_scene=True, scene_count_hint=2)
    manifest = seeded["manifest"]
    paths = seeded["paths"]
    file_repository = seeded["file_repository"]
    sqlite_repository = seeded["sqlite_repository"]
    planner_service = seeded["planner_service"]
    bible_service = seeded["bible_service"]
    llm_gateway = seeded["llm_gateway"]

    path = path_getter(paths, manifest.slug)
    payload = file_repository.read_json(path)
    status_field = "outline_status" if target == "outline" else "status"
    payload[status_field] = "draft"
    file_repository.write_json(path, payload)

    context_service = ContextBundleService(paths, file_repository, bible_service, planner_service)
    memory_service = MemoryStubService(paths, file_repository)
    draft_service = SceneDraftService(
        paths,
        file_repository,
        sqlite_repository,
        bible_service,
        planner_service,
        context_service,
        memory_service,
        llm_gateway,
    )

    with pytest.raises(ConflictError):
        draft_service.generate(manifest.project_id, seeded["scene_id"], mode="outline_strict")


def test_generate_is_deterministic_and_supersedes_previous_draft(service_container) -> None:
    from backend.app.services.context_bundle_service import ContextBundleService
    from backend.app.services.memory_stub_service import MemoryStubService
    from backend.app.services.scene_draft_service import SceneDraftService

    container = service_container
    seeded = container["seed_project"](ready_scene=True, scene_count_hint=2)
    manifest = seeded["manifest"]
    paths = seeded["paths"]
    file_repository = seeded["file_repository"]
    sqlite_repository = seeded["sqlite_repository"]
    planner_service = seeded["planner_service"]
    bible_service = seeded["bible_service"]
    llm_gateway = seeded["llm_gateway"]

    context_service = ContextBundleService(paths, file_repository, bible_service, planner_service)
    memory_service = MemoryStubService(paths, file_repository)
    draft_service = SceneDraftService(
        paths,
        file_repository,
        sqlite_repository,
        bible_service,
        planner_service,
        context_service,
        memory_service,
        llm_gateway,
    )

    first = draft_service.generate(manifest.project_id, seeded["scene_id"], mode="outline_strict")
    second = draft_service.generate(manifest.project_id, seeded["scene_id"], mode="outline_strict")

    assert first.content_md == second.content_md
    assert first.summary == second.summary
    first_reloaded = draft_service.get_draft(manifest.project_id, first.draft_id)
    manifest_payload = draft_service.get_scene_manifest(manifest.project_id, seeded["scene_id"])
    assert first_reloaded.status == "superseded"
    assert manifest_payload.latest_draft_id == second.draft_id
    assert manifest_payload.accepted_draft_id is None


def test_accept_reject_are_strict_and_manifest_stays_consistent(service_container) -> None:
    from backend.app.services.context_bundle_service import ContextBundleService
    from backend.app.services.memory_stub_service import MemoryStubService
    from backend.app.services.scene_draft_service import SceneDraftService
    from backend.app.services.exceptions import ConflictError

    container = service_container
    seeded = container["seed_project"](ready_scene=True, scene_count_hint=2)
    manifest = seeded["manifest"]
    paths = seeded["paths"]
    file_repository = seeded["file_repository"]
    sqlite_repository = seeded["sqlite_repository"]
    planner_service = seeded["planner_service"]
    bible_service = seeded["bible_service"]
    llm_gateway = seeded["llm_gateway"]

    context_service = ContextBundleService(paths, file_repository, bible_service, planner_service)
    memory_service = MemoryStubService(paths, file_repository)
    draft_service = SceneDraftService(
        paths,
        file_repository,
        sqlite_repository,
        bible_service,
        planner_service,
        context_service,
        memory_service,
        llm_gateway,
    )

    draft_one = draft_service.generate(manifest.project_id, seeded["scene_id"], mode="outline_strict")
    rejected = draft_service.reject(manifest.project_id, draft_one.draft_id)
    scene_manifest = draft_service.get_scene_manifest(manifest.project_id, seeded["scene_id"])
    assert rejected.status == "rejected"
    assert scene_manifest.latest_draft_id == draft_one.draft_id
    assert scene_manifest.accepted_draft_id is None
    with pytest.raises(ConflictError):
        draft_service.reject(manifest.project_id, draft_one.draft_id)
    with pytest.raises(ConflictError):
        draft_service.accept(manifest.project_id, draft_one.draft_id)

    draft_two = draft_service.generate(manifest.project_id, seeded["scene_id"], mode="momentum")
    accepted_two = draft_service.accept(manifest.project_id, draft_two.draft_id)
    scene_manifest = draft_service.get_scene_manifest(manifest.project_id, seeded["scene_id"])
    assert accepted_two.status == "accepted"
    assert scene_manifest.latest_draft_id == draft_two.draft_id
    assert scene_manifest.accepted_draft_id == draft_two.draft_id
    with pytest.raises(ConflictError):
        draft_service.accept(manifest.project_id, draft_two.draft_id)
    with pytest.raises(ConflictError):
        draft_service.reject(manifest.project_id, draft_two.draft_id)

    draft_three = draft_service.generate(manifest.project_id, seeded["scene_id"], mode="outline_strict")
    accepted_three = draft_service.accept(manifest.project_id, draft_three.draft_id)
    previous = draft_service.get_draft(manifest.project_id, draft_two.draft_id)
    scene_manifest = draft_service.get_scene_manifest(manifest.project_id, seeded["scene_id"])
    assert accepted_three.status == "accepted"
    assert previous.status == "superseded"
    assert scene_manifest.latest_draft_id == draft_three.draft_id
    assert scene_manifest.accepted_draft_id == draft_three.draft_id
