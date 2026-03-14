from __future__ import annotations

from fastapi import APIRouter, Body, Depends, HTTPException, status

from backend.app.core.dependencies import (
    get_app_paths,
    get_app_settings,
    get_bible_service,
    get_book_assembly_service,
    get_book_checks_service,
    get_book_continuity_checks_service,
    get_chapter_assembly_service,
    get_chapter_checks_service,
    get_checks_service,
    get_context_bundle_service,
    get_export_service,
    get_file_repository,
    get_import_service,
    get_llm_gateway,
    get_memory_service,
    get_planner_service,
    get_project_health_service,
    get_project_snapshot_service,
    get_rebuild_service,
    get_retrieval_service,
    get_scene_draft_service,
    get_sqlite_repository,
    get_style_service,
    get_voice_constraint_builder,
    get_volume_assembly_service,
    get_volume_checks_service,
)
from backend.app.domain.models.writing import (
    ExportResult,
    ImportReport,
    ProjectHealthReport,
    RebuildReport,
    SnapshotListResponse,
    SnapshotResult,
)
from backend.app.schemas.productization import (
    ArchiveSnapshotRequest,
    BackupProjectRequest,
    ExportProjectRequest,
    ImportProjectPackageRequest,
    RebuildProjectRequest,
)
from backend.app.services.exceptions import ConflictError

router = APIRouter(tags=["productization"])
project_router = APIRouter(prefix="/api/projects/{project_id}", tags=["productization"])


def _error_detail(code: str, message: str) -> dict[str, str]:
    return {"code": code, "message": message}


def _value_error_code(message: str) -> str:
    mapping = {
        "Unsupported export scope.": "unsupported_export_scope",
        "Unsupported export format.": "unsupported_export_format",
        "Unsupported rebuild targets.": "unsupported_rebuild_targets",
        "target_id is required for this export scope.": "missing_target_id",
        "Only create_new import mode is supported.": "unsupported_import_mode",
        "Unsupported package_version.": "unsupported_package_version",
        "Manifest and inventory package_id mismatch.": "package_manifest_mismatch",
        "Inventory contains absolute path.": "package_path_invalid",
        "Inventory contains invalid relative path.": "package_path_invalid",
        "Inventory contains machine-specific path.": "package_path_invalid",
    }
    if message in mapping:
        return mapping[message]
    if message.startswith("Missing required canonical file:"):
        return "package_canonical_missing"
    if message.startswith("Inventory-declared file missing:"):
        return "package_inventory_missing_file"
    if message.startswith("Hash mismatch for "):
        return "package_hash_mismatch"
    if message.startswith("Size mismatch for "):
        return "package_size_mismatch"
    if message.startswith("Unsupported package path:"):
        return "package_path_invalid"
    return "invalid_request"


def _conflict_error_code(message: str) -> str:
    mapping = {
        "Scene export requires exactly one active accepted draft.": "scene_export_requires_single_accepted",
        "Chapter export requires an assembled chapter artifact.": "chapter_export_unavailable",
        "Volume export requires an assembled volume artifact.": "volume_export_unavailable",
        "Book export requires an assembled book artifact.": "book_export_unavailable",
        "Only project packages can be imported.": "project_package_required",
        "Target project_id already exists.": "target_project_exists",
        "Target project slug already exists.": "target_slug_exists",
    }
    return mapping.get(message, "conflict")


def _build_services(settings):
    paths = get_app_paths(settings)
    file_repository = get_file_repository()
    sqlite_repository = get_sqlite_repository(paths)
    bible_service = get_bible_service(paths, file_repository, sqlite_repository)
    planner_service = get_planner_service(paths, file_repository, sqlite_repository, bible_service)
    style_service = get_style_service(paths, file_repository, sqlite_repository)
    voice_constraint_builder = get_voice_constraint_builder(style_service)
    retrieval_service = get_retrieval_service(paths, file_repository, sqlite_repository, planner_service)
    context_bundle_service = get_context_bundle_service(
        paths,
        file_repository,
        bible_service,
        planner_service,
        retrieval_service,
        voice_constraint_builder,
    )
    checks_service = get_checks_service(paths, file_repository, sqlite_repository, bible_service, planner_service, context_bundle_service)
    memory_service = get_memory_service(paths, file_repository, bible_service)
    llm_gateway = get_llm_gateway(settings)
    draft_service = get_scene_draft_service(
        paths,
        file_repository,
        sqlite_repository,
        bible_service,
        planner_service,
        context_bundle_service,
        memory_service,
        checks_service,
        style_service,
        llm_gateway,
    )
    chapter_checks_service = get_chapter_checks_service(paths, file_repository, sqlite_repository, planner_service, draft_service)
    chapter_service = get_chapter_assembly_service(
        paths,
        file_repository,
        sqlite_repository,
        planner_service,
        draft_service,
        memory_service,
        chapter_checks_service,
    )
    volume_checks_service = get_volume_checks_service(paths, file_repository, sqlite_repository, planner_service)
    volume_service = get_volume_assembly_service(
        paths,
        file_repository,
        sqlite_repository,
        planner_service,
        chapter_service,
        memory_service,
        volume_checks_service,
    )
    book_checks_service = get_book_checks_service(paths, file_repository, sqlite_repository, planner_service)
    continuity_service = get_book_continuity_checks_service(
        paths,
        file_repository,
        sqlite_repository,
        bible_service,
        planner_service,
    )
    book_service = get_book_assembly_service(
        paths,
        file_repository,
        sqlite_repository,
        planner_service,
        volume_service,
        memory_service,
        book_checks_service,
        continuity_service,
    )
    export_service = get_export_service(paths, file_repository, sqlite_repository, planner_service)
    rebuild_service = get_rebuild_service(
        paths,
        file_repository,
        sqlite_repository,
        bible_service,
        planner_service,
        checks_service,
        chapter_checks_service,
        volume_checks_service,
        book_checks_service,
        continuity_service,
        chapter_service,
        volume_service,
        book_service,
    )
    health_service = get_project_health_service(paths, file_repository, sqlite_repository, bible_service, planner_service)
    import_service = get_import_service(
        paths,
        file_repository,
        sqlite_repository,
        bible_service,
        planner_service,
        health_service,
    )
    snapshot_service = get_project_snapshot_service(
        paths,
        file_repository,
        sqlite_repository,
        export_service,
    )
    return export_service, rebuild_service, health_service, import_service, snapshot_service


def _map_error(error: Exception) -> HTTPException:
    if isinstance(error, KeyError):
        return HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=_error_detail("resource_not_found", "Project or resource not found"),
        )
    if isinstance(error, ConflictError):
        message = str(error)
        return HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=_error_detail(_conflict_error_code(message), message),
        )
    if isinstance(error, ValueError):
        message = str(error)
        return HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=_error_detail(_value_error_code(message), message),
        )
    raise error


@project_router.post("/export", response_model=ExportResult)
def export_project_artifact(
    project_id: str,
    request: ExportProjectRequest = Body(...),
    settings=Depends(get_app_settings),
) -> ExportResult:
    export_service, _, _, _, _ = _build_services(settings)
    try:
        return export_service.export(project_id, request.scope, request.target_id, request.format)
    except Exception as error:
        raise _map_error(error) from error


@project_router.post("/rebuild", response_model=RebuildReport)
def rebuild_project(
    project_id: str,
    request: RebuildProjectRequest | None = Body(default=None),
    settings=Depends(get_app_settings),
) -> RebuildReport:
    _, rebuild_service, _, _, _ = _build_services(settings)
    try:
        request = request or RebuildProjectRequest()
        return rebuild_service.rebuild(project_id, request.targets)
    except Exception as error:
        raise _map_error(error) from error


@project_router.get("/diagnostics/health", response_model=ProjectHealthReport)
def get_project_health(project_id: str, settings=Depends(get_app_settings)) -> ProjectHealthReport:
    _, _, health_service, _, _ = _build_services(settings)
    try:
        return health_service.build_report(project_id)
    except Exception as error:
        raise _map_error(error) from error


@router.post("/api/projects/import-package", response_model=ImportReport)
def import_project_package(
    request: ImportProjectPackageRequest = Body(...),
    settings=Depends(get_app_settings),
) -> ImportReport:
    _, _, _, import_service, _ = _build_services(settings)
    try:
        return import_service.import_package(
            request.package_path,
            new_project_id=request.new_project_id,
            new_project_slug=request.new_project_slug,
            mode=request.mode,
        )
    except Exception as error:
        raise _map_error(error) from error


@project_router.post("/archive-snapshot", response_model=SnapshotResult)
def create_archive_snapshot(
    project_id: str,
    request: ArchiveSnapshotRequest = Body(default=ArchiveSnapshotRequest()),
    settings=Depends(get_app_settings),
) -> SnapshotResult:
    _, _, _, _, snapshot_service = _build_services(settings)
    try:
        return snapshot_service.create_archive_snapshot(project_id, label=request.label, format=request.format)
    except Exception as error:
        raise _map_error(error) from error


@project_router.post("/backup", response_model=SnapshotResult)
def create_backup(
    project_id: str,
    request: BackupProjectRequest = Body(default=BackupProjectRequest()),
    settings=Depends(get_app_settings),
) -> SnapshotResult:
    _, _, _, _, snapshot_service = _build_services(settings)
    try:
        return snapshot_service.create_backup(project_id, format=request.format)
    except Exception as error:
        raise _map_error(error) from error


@project_router.get("/snapshots", response_model=SnapshotListResponse)
def list_snapshots(project_id: str, settings=Depends(get_app_settings)) -> SnapshotListResponse:
    _, _, _, _, snapshot_service = _build_services(settings)
    try:
        return SnapshotListResponse(items=snapshot_service.list_snapshots(project_id))
    except Exception as error:
        raise _map_error(error) from error


router.include_router(project_router)
