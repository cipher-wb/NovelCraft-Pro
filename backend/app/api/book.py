from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from backend.app.core.dependencies import (
    get_app_paths,
    get_app_settings,
    get_bible_service,
    get_book_assembly_service,
    get_book_checks_service,
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
    get_volume_assembly_service,
    get_volume_checks_service,
)
from backend.app.domain.models.writing import BookAssembledDocument
from backend.app.schemas.books import BookAssemblyDetailResponse, BookCheckReportResponse
from backend.app.services.exceptions import ConflictError

router = APIRouter(prefix="/api/projects/{project_id}/book", tags=["book"])


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
    book_service = get_book_assembly_service(
        paths,
        file_repository,
        sqlite_repository,
        planner_service,
        volume_service,
        memory_service,
        book_checks_service,
    )
    return book_service, book_checks_service


def _map_error(error: Exception) -> HTTPException:
    if isinstance(error, KeyError):
        return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project or resource not found")
    if isinstance(error, ConflictError):
        return HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error))
    if isinstance(error, ValueError):
        return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(error))
    raise error


@router.post("/assemble", response_model=BookAssemblyDetailResponse)
def assemble_book(project_id: str, settings=Depends(get_app_settings)) -> BookAssemblyDetailResponse:
    book_service, book_checks_service = _build_services(settings)
    try:
        assembled = book_service.assemble(project_id)
        report = book_checks_service.get_latest_report(project_id)
        return BookAssemblyDetailResponse(assembled=assembled, check_report=report)
    except Exception as error:
        raise _map_error(error) from error


@router.get("/assembled", response_model=BookAssembledDocument)
def get_assembled_book(project_id: str, settings=Depends(get_app_settings)) -> BookAssembledDocument:
    book_service, _ = _build_services(settings)
    try:
        return book_service.get_assembled(project_id)
    except Exception as error:
        raise _map_error(error) from error


@router.get("/checks/latest", response_model=BookCheckReportResponse)
def get_latest_book_check_report(project_id: str, settings=Depends(get_app_settings)) -> BookCheckReportResponse:
    _, book_checks_service = _build_services(settings)
    try:
        report = book_checks_service.get_latest_report(project_id)
        if report is None:
            raise KeyError(project_id)
        return BookCheckReportResponse(report=report)
    except Exception as error:
        raise _map_error(error) from error


@router.post("/checks/recheck", response_model=BookCheckReportResponse)
def recheck_book(project_id: str, settings=Depends(get_app_settings)) -> BookCheckReportResponse:
    book_service, _ = _build_services(settings)
    try:
        report = book_service.recheck(project_id)
        return BookCheckReportResponse(report=report)
    except Exception as error:
        raise _map_error(error) from error


@router.post("/finalize", response_model=BookAssemblyDetailResponse)
def finalize_book(project_id: str, settings=Depends(get_app_settings)) -> BookAssemblyDetailResponse:
    book_service, book_checks_service = _build_services(settings)
    try:
        assembled = book_service.finalize(project_id)
        report = book_checks_service.get_latest_report(project_id)
        return BookAssemblyDetailResponse(assembled=assembled, check_report=report)
    except Exception as error:
        raise _map_error(error) from error
