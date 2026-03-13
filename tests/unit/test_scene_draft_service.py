from __future__ import annotations

import pytest



def _build_draft_service(seeded):
    from backend.app.services.checks_service import ChecksService
    from backend.app.services.context_bundle_service import ContextBundleService
    from backend.app.services.memory_service import MemoryService
    from backend.app.services.retrieval_service import RetrievalService
    from backend.app.services.scene_draft_service import SceneDraftService

    paths = seeded["paths"]
    file_repository = seeded["file_repository"]
    sqlite_repository = seeded["sqlite_repository"]
    planner_service = seeded["planner_service"]
    bible_service = seeded["bible_service"]
    llm_gateway = seeded["llm_gateway"]

    retrieval_service = RetrievalService(paths, file_repository, sqlite_repository, planner_service)
    context_service = ContextBundleService(paths, file_repository, bible_service, planner_service, retrieval_service)
    checks_service = ChecksService(paths, file_repository, sqlite_repository, bible_service, planner_service, context_service)
    memory_service = MemoryService(paths, file_repository, bible_service)
    return SceneDraftService(
        paths,
        file_repository,
        sqlite_repository,
        bible_service,
        planner_service,
        context_service,
        memory_service,
        checks_service,
        llm_gateway,
    )


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
    from backend.app.services.exceptions import ConflictError

    container = service_container
    seeded = container["seed_project"](ready_scene=True, scene_count_hint=2)
    manifest = seeded["manifest"]
    paths = seeded["paths"]
    file_repository = seeded["file_repository"]

    path = path_getter(paths, manifest.slug)
    payload = file_repository.read_json(path)
    payload["status"] = "draft"
    file_repository.write_json(path, payload)

    draft_service = _build_draft_service(seeded)

    with pytest.raises(ConflictError):
        draft_service.generate(manifest.project_id, seeded["scene_id"], mode="outline_strict")



def test_generate_is_deterministic_and_supersedes_previous_draft(service_container) -> None:
    container = service_container
    seeded = container["seed_project"](ready_scene=True, scene_count_hint=2)
    manifest = seeded["manifest"]
    draft_service = _build_draft_service(seeded)

    first = draft_service.generate(manifest.project_id, seeded["scene_id"], mode="outline_strict")
    second = draft_service.generate(manifest.project_id, seeded["scene_id"], mode="outline_strict")

    assert first.content_md == second.content_md
    assert first.summary == second.summary
    first_reloaded = draft_service.get_draft(manifest.project_id, first.draft_id)
    manifest_payload = draft_service.get_scene_manifest(manifest.project_id, seeded["scene_id"])
    assert first_reloaded.status == "superseded"
    assert manifest_payload.latest_draft_id == second.draft_id
    assert manifest_payload.accepted_draft_id is None
    assert second.latest_check_run_id is not None
    assert second.last_check_status == "clean"



def test_accept_reject_are_strict_and_manifest_stays_consistent(service_container) -> None:
    from backend.app.services.exceptions import ConflictError

    container = service_container
    seeded = container["seed_project"](ready_scene=True, scene_count_hint=2)
    manifest = seeded["manifest"]
    draft_service = _build_draft_service(seeded)

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


def test_repaired_draft_accept_and_reject_reuse_existing_mainline(service_container) -> None:
    seeded = service_container["seed_project"](ready_scene=True, scene_count_hint=2)
    manifest = seeded["manifest"]
    paths = seeded["paths"]
    file_repository = seeded["file_repository"]
    draft_service = _build_draft_service(seeded)

    from backend.app.services.checks_service import ChecksService
    from backend.app.services.context_bundle_service import ContextBundleService
    from backend.app.services.memory_service import MemoryService
    from backend.app.services.repair_service import RepairService
    from backend.app.services.retrieval_service import RetrievalService

    retrieval_service = RetrievalService(paths, file_repository, seeded["sqlite_repository"], seeded["planner_service"])
    context_service = ContextBundleService(paths, file_repository, seeded["bible_service"], seeded["planner_service"], retrieval_service)
    checks_service = ChecksService(paths, file_repository, seeded["sqlite_repository"], seeded["bible_service"], seeded["planner_service"], context_service)
    repair_service = RepairService(
        paths,
        file_repository,
        seeded["sqlite_repository"],
        seeded["planner_service"],
        draft_service,
        context_service,
        checks_service,
        seeded["llm_gateway"],
    )

    source = draft_service.generate(manifest.project_id, seeded["scene_id"], mode="outline_strict")
    payload = source.model_dump(mode="json")
    payload["content_md"] = "空白文本"
    payload["summary"] = "空白摘要"
    payload["updated_at"] = "2026-03-12T12:00:00+00:00"
    file_repository.write_json(paths.project_root(manifest.slug) / source.draft_path, payload)

    repaired = repair_service.repair_draft(manifest.project_id, source.draft_id)
    rejected = draft_service.reject(manifest.project_id, repaired.draft_id)
    assert rejected.status == "rejected"

    source_two = draft_service.generate(manifest.project_id, seeded["scene_id"], mode="momentum")
    payload_two = source_two.model_dump(mode="json")
    payload_two["content_md"] = "空白文本"
    payload_two["summary"] = "空白摘要"
    payload_two["updated_at"] = "2026-03-12T12:00:00+00:00"
    file_repository.write_json(paths.project_root(manifest.slug) / source_two.draft_path, payload_two)
    repaired_two = repair_service.repair_draft(manifest.project_id, source_two.draft_id)
    accepted = draft_service.accept(manifest.project_id, repaired_two.draft_id)
    scene_manifest = draft_service.get_scene_manifest(manifest.project_id, seeded["scene_id"])

    assert accepted.status == "accepted"
    assert scene_manifest.accepted_draft_id == repaired_two.draft_id
    assert accepted.memory_stub_record_id is not None
