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
    get_llm_gateway,
    get_memory_service,
    get_planner_service,
    get_project_health_service,
    get_rebuild_service,
    get_retrieval_service,
    get_scene_draft_service,
    get_sqlite_repository,
    get_style_service,
    get_voice_constraint_builder,
    get_volume_assembly_service,
    get_volume_checks_service,
)
from backend.app.domain.models.writing import ExportResult, ProjectHealthReport, RebuildReport
from backend.app.schemas.productization import ExportProjectRequest, RebuildProjectRequest
from backend.app.services.exceptions import ConflictError

router = APIRouter(prefix="/api/projects/{project_id}", tags=["productization"])


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
    return export_service, rebuild_service, health_service


def _map_error(error: Exception) -> HTTPException:
    if isinstance(error, KeyError):
        return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project or resource not found")
    if isinstance(error, ConflictError):
        return HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error))
    if isinstance(error, ValueError):
        return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(error))
    raise error


@router.post("/export", response_model=ExportResult)
def export_project_artifact(
    project_id: str,
    request: ExportProjectRequest = Body(...),
    settings=Depends(get_app_settings),
) -> ExportResult:
    export_service, _, _ = _build_services(settings)
    try:
        return export_service.export(project_id, request.scope, request.target_id, request.format)
    except Exception as error:
        raise _map_error(error) from error


@router.post("/rebuild", response_model=RebuildReport)
def rebuild_project(
    project_id: str,
    request: RebuildProjectRequest | None = Body(default=None),
    settings=Depends(get_app_settings),
) -> RebuildReport:
    _, rebuild_service, _ = _build_services(settings)
    try:
        request = request or RebuildProjectRequest()
        return rebuild_service.rebuild(project_id, request.targets)
    except Exception as error:
        raise _map_error(error) from error


@router.get("/diagnostics/health", response_model=ProjectHealthReport)
def get_project_health(project_id: str, settings=Depends(get_app_settings)) -> ProjectHealthReport:
    _, _, health_service = _build_services(settings)
    try:
        return health_service.build_report(project_id)
    except Exception as error:
        raise _map_error(error) from error
