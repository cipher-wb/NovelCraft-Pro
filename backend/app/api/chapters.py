from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from backend.app.core.dependencies import (
    get_app_paths,
    get_app_settings,
    get_bible_service,
    get_chapter_assembly_service,
    get_chapter_checks_service,
    get_checks_service,
    get_context_bundle_service,
    get_file_repository,
    get_llm_gateway,
    get_memory_service,
    get_planner_service,
    get_retrieval_service,
    get_scene_draft_service,
    get_sqlite_repository,
    get_style_service,
    get_voice_constraint_builder,
)
from backend.app.domain.models.writing import ChapterAssembledDocument
from backend.app.schemas.chapters import ChapterAssemblyDetailResponse, ChapterCheckReportResponse
from backend.app.services.exceptions import ConflictError

router = APIRouter(prefix="/api/projects/{project_id}/chapters", tags=["chapters"])


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
    scene_draft_service = get_scene_draft_service(
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
    chapter_checks_service = get_chapter_checks_service(paths, file_repository, sqlite_repository, planner_service, scene_draft_service)
    chapter_assembly_service = get_chapter_assembly_service(
        paths,
        file_repository,
        sqlite_repository,
        planner_service,
        scene_draft_service,
        memory_service,
        chapter_checks_service,
    )
    return chapter_assembly_service, chapter_checks_service


def _map_error(error: Exception) -> HTTPException:
    if isinstance(error, KeyError):
        return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project or resource not found")
    if isinstance(error, ConflictError):
        return HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error))
    if isinstance(error, ValueError):
        return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(error))
    raise error


@router.post("/{chapter_id}/assemble", response_model=ChapterAssemblyDetailResponse)
def assemble_chapter(project_id: str, chapter_id: str, settings=Depends(get_app_settings)) -> ChapterAssemblyDetailResponse:
    chapter_service, chapter_checks_service = _build_services(settings)
    try:
        assembled = chapter_service.assemble(project_id, chapter_id)
        report = chapter_checks_service.get_latest_report(project_id, chapter_id)
        return ChapterAssemblyDetailResponse(assembled=assembled, check_report=report)
    except Exception as error:
        raise _map_error(error) from error


@router.get("/{chapter_id}/assembled", response_model=ChapterAssembledDocument)
def get_assembled_chapter(project_id: str, chapter_id: str, settings=Depends(get_app_settings)) -> ChapterAssembledDocument:
    chapter_service, _ = _build_services(settings)
    try:
        return chapter_service.get_assembled(project_id, chapter_id)
    except Exception as error:
        raise _map_error(error) from error


@router.get("/{chapter_id}/checks/latest", response_model=ChapterCheckReportResponse)
def get_latest_chapter_check_report(project_id: str, chapter_id: str, settings=Depends(get_app_settings)) -> ChapterCheckReportResponse:
    _, chapter_checks_service = _build_services(settings)
    try:
        report = chapter_checks_service.get_latest_report(project_id, chapter_id)
        if report is None:
            raise KeyError(chapter_id)
        return ChapterCheckReportResponse(report=report)
    except Exception as error:
        raise _map_error(error) from error


@router.post("/{chapter_id}/checks/recheck", response_model=ChapterCheckReportResponse)
def recheck_chapter(project_id: str, chapter_id: str, settings=Depends(get_app_settings)) -> ChapterCheckReportResponse:
    chapter_service, _ = _build_services(settings)
    try:
        report = chapter_service.recheck(project_id, chapter_id)
        return ChapterCheckReportResponse(report=report)
    except Exception as error:
        raise _map_error(error) from error


@router.post("/{chapter_id}/finalize", response_model=ChapterAssemblyDetailResponse)
def finalize_chapter(project_id: str, chapter_id: str, settings=Depends(get_app_settings)) -> ChapterAssemblyDetailResponse:
    chapter_service, chapter_checks_service = _build_services(settings)
    try:
        assembled = chapter_service.finalize(project_id, chapter_id)
        report = chapter_checks_service.get_latest_report(project_id, chapter_id)
        return ChapterAssemblyDetailResponse(assembled=assembled, check_report=report)
    except Exception as error:
        raise _map_error(error) from error
