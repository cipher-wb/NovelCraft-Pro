from __future__ import annotations

from fastapi import APIRouter, Body, Depends, HTTPException, status

from backend.app.core.dependencies import (
    get_app_paths,
    get_app_settings,
    get_bible_service,
    get_checks_service,
    get_context_bundle_service,
    get_file_repository,
    get_llm_gateway,
    get_memory_service,
    get_planner_service,
    get_repair_service,
    get_retrieval_service,
    get_scene_draft_service,
    get_sqlite_repository,
)
from backend.app.domain.models.writing import SceneDraftManifest
from backend.app.schemas.checks import DraftCheckReportResponse
from backend.app.schemas.drafts import GenerateSceneDraftRequest, RepairDraftRequest, SceneDraftDetailResponse
from backend.app.services.exceptions import ConflictError

router = APIRouter(prefix="/api/projects/{project_id}/drafts", tags=["drafts"])



def _build_services(settings):
    paths = get_app_paths(settings)
    file_repository = get_file_repository()
    sqlite_repository = get_sqlite_repository(paths)
    bible_service = get_bible_service(paths, file_repository, sqlite_repository)
    planner_service = get_planner_service(paths, file_repository, sqlite_repository, bible_service)
    retrieval_service = get_retrieval_service(paths, file_repository, sqlite_repository, planner_service)
    context_bundle_service = get_context_bundle_service(paths, file_repository, bible_service, planner_service, retrieval_service)
    memory_service = get_memory_service(paths, file_repository, bible_service)
    checks_service = get_checks_service(paths, file_repository, sqlite_repository, bible_service, planner_service, context_bundle_service)
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
        llm_gateway,
    )
    repair_service = get_repair_service(
        paths,
        file_repository,
        sqlite_repository,
        planner_service,
        draft_service,
        context_bundle_service,
        checks_service,
        llm_gateway,
    )
    return draft_service, checks_service, repair_service



def _map_error(error: Exception) -> HTTPException:
    if isinstance(error, KeyError):
        return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project or resource not found")
    if isinstance(error, ConflictError):
        return HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error))
    if isinstance(error, ValueError):
        return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(error))
    raise error


@router.post("/scenes/{scene_id}/generate", response_model=SceneDraftDetailResponse, status_code=status.HTTP_201_CREATED)
def generate_scene_draft(
    project_id: str,
    scene_id: str,
    request: GenerateSceneDraftRequest | None = Body(default=None),
    settings=Depends(get_app_settings),
) -> SceneDraftDetailResponse:
    draft_service, checks_service, _ = _build_services(settings)
    request = request or GenerateSceneDraftRequest()
    try:
        draft = draft_service.generate(project_id, scene_id, request.mode)
        bundle = draft_service.get_context_bundle_for_draft(project_id, draft.draft_id)
        report = checks_service.get_latest_report(project_id, draft.draft_id)
        return SceneDraftDetailResponse(draft=draft, context_bundle=bundle, check_report=report)
    except Exception as error:
        raise _map_error(error) from error


@router.get("/scenes/{scene_id}", response_model=SceneDraftManifest)
def get_scene_manifest(project_id: str, scene_id: str, settings=Depends(get_app_settings)) -> SceneDraftManifest:
    draft_service, _, _ = _build_services(settings)
    try:
        return draft_service.get_scene_manifest(project_id, scene_id)
    except Exception as error:
        raise _map_error(error) from error


@router.get("/{draft_id}", response_model=SceneDraftDetailResponse)
def get_draft(project_id: str, draft_id: str, settings=Depends(get_app_settings)) -> SceneDraftDetailResponse:
    draft_service, checks_service, _ = _build_services(settings)
    try:
        draft = draft_service.get_draft(project_id, draft_id)
        bundle = draft_service.get_context_bundle_for_draft(project_id, draft_id)
        report = checks_service.get_latest_report(project_id, draft_id)
        return SceneDraftDetailResponse(draft=draft, context_bundle=bundle, check_report=report)
    except Exception as error:
        raise _map_error(error) from error


@router.get("/{draft_id}/checks/latest", response_model=DraftCheckReportResponse)
def get_latest_check_report(project_id: str, draft_id: str, settings=Depends(get_app_settings)) -> DraftCheckReportResponse:
    _, checks_service, _ = _build_services(settings)
    try:
        report = checks_service.get_latest_report(project_id, draft_id)
        if report is None:
            raise KeyError(draft_id)
        return DraftCheckReportResponse(report=report)
    except Exception as error:
        raise _map_error(error) from error


@router.post("/{draft_id}/checks/recheck", response_model=DraftCheckReportResponse)
def recheck_draft(project_id: str, draft_id: str, settings=Depends(get_app_settings)) -> DraftCheckReportResponse:
    draft_service, _, _ = _build_services(settings)
    try:
        report = draft_service.recheck_checks(project_id, draft_id)
        return DraftCheckReportResponse(report=report)
    except Exception as error:
        raise _map_error(error) from error


@router.post("/{draft_id}/repair", response_model=SceneDraftDetailResponse)
def repair_draft(
    project_id: str,
    draft_id: str,
    request: RepairDraftRequest | None = Body(default=None),
    settings=Depends(get_app_settings),
) -> SceneDraftDetailResponse:
    draft_service, checks_service, repair_service = _build_services(settings)
    request = request or RepairDraftRequest()
    try:
        draft = repair_service.repair_draft(project_id, draft_id, issue_ids=request.issue_ids)
        bundle = draft_service.get_context_bundle_for_draft(project_id, draft.draft_id)
        report = checks_service.get_latest_report(project_id, draft.draft_id)
        return SceneDraftDetailResponse(draft=draft, context_bundle=bundle, check_report=report)
    except Exception as error:
        raise _map_error(error) from error


@router.post("/{draft_id}/accept", response_model=SceneDraftDetailResponse)
def accept_draft(project_id: str, draft_id: str, settings=Depends(get_app_settings)) -> SceneDraftDetailResponse:
    draft_service, checks_service, _ = _build_services(settings)
    try:
        draft = draft_service.accept(project_id, draft_id)
        bundle = draft_service.get_context_bundle_for_draft(project_id, draft_id)
        report = checks_service.get_latest_report(project_id, draft_id)
        return SceneDraftDetailResponse(draft=draft, context_bundle=bundle, check_report=report)
    except Exception as error:
        raise _map_error(error) from error


@router.post("/{draft_id}/reject", response_model=SceneDraftDetailResponse)
def reject_draft(project_id: str, draft_id: str, settings=Depends(get_app_settings)) -> SceneDraftDetailResponse:
    draft_service, checks_service, _ = _build_services(settings)
    try:
        draft = draft_service.reject(project_id, draft_id)
        bundle = draft_service.get_context_bundle_for_draft(project_id, draft_id)
        report = checks_service.get_latest_report(project_id, draft_id)
        return SceneDraftDetailResponse(draft=draft, context_bundle=bundle, check_report=report)
    except Exception as error:
        raise _map_error(error) from error
