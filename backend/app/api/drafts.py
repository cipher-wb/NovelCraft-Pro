from __future__ import annotations

from fastapi import APIRouter, Body, Depends, HTTPException, status

from backend.app.core.dependencies import (
    get_app_paths,
    get_app_settings,
    get_bible_service,
    get_context_bundle_service,
    get_file_repository,
    get_llm_gateway,
    get_memory_stub_service,
    get_planner_service,
    get_scene_draft_service,
    get_sqlite_repository,
)
from backend.app.domain.models.writing import SceneDraftManifest
from backend.app.schemas.drafts import GenerateSceneDraftRequest, SceneDraftDetailResponse
from backend.app.services.exceptions import ConflictError

router = APIRouter(prefix="/api/projects/{project_id}/drafts", tags=["drafts"])


def _get_service(settings):
    paths = get_app_paths(settings)
    file_repository = get_file_repository()
    sqlite_repository = get_sqlite_repository(paths)
    bible_service = get_bible_service(paths, file_repository, sqlite_repository)
    planner_service = get_planner_service(paths, file_repository, sqlite_repository, bible_service)
    context_bundle_service = get_context_bundle_service(paths, file_repository, bible_service, planner_service)
    memory_stub_service = get_memory_stub_service(paths, file_repository)
    llm_gateway = get_llm_gateway(settings)
    return get_scene_draft_service(
        paths,
        file_repository,
        sqlite_repository,
        bible_service,
        planner_service,
        context_bundle_service,
        memory_stub_service,
        llm_gateway,
    )


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
    service = _get_service(settings)
    request = request or GenerateSceneDraftRequest()
    try:
        draft = service.generate(project_id, scene_id, request.mode)
        bundle = service.get_context_bundle_for_draft(project_id, draft.draft_id)
        return SceneDraftDetailResponse(draft=draft, context_bundle=bundle)
    except Exception as error:
        raise _map_error(error) from error


@router.get("/scenes/{scene_id}", response_model=SceneDraftManifest)
def get_scene_manifest(project_id: str, scene_id: str, settings=Depends(get_app_settings)) -> SceneDraftManifest:
    service = _get_service(settings)
    try:
        return service.get_scene_manifest(project_id, scene_id)
    except Exception as error:
        raise _map_error(error) from error


@router.get("/{draft_id}", response_model=SceneDraftDetailResponse)
def get_draft(project_id: str, draft_id: str, settings=Depends(get_app_settings)) -> SceneDraftDetailResponse:
    service = _get_service(settings)
    try:
        draft = service.get_draft(project_id, draft_id)
        bundle = service.get_context_bundle_for_draft(project_id, draft_id)
        return SceneDraftDetailResponse(draft=draft, context_bundle=bundle)
    except Exception as error:
        raise _map_error(error) from error


@router.post("/{draft_id}/accept", response_model=SceneDraftDetailResponse)
def accept_draft(project_id: str, draft_id: str, settings=Depends(get_app_settings)) -> SceneDraftDetailResponse:
    service = _get_service(settings)
    try:
        draft = service.accept(project_id, draft_id)
        bundle = service.get_context_bundle_for_draft(project_id, draft_id)
        return SceneDraftDetailResponse(draft=draft, context_bundle=bundle)
    except Exception as error:
        raise _map_error(error) from error


@router.post("/{draft_id}/reject", response_model=SceneDraftDetailResponse)
def reject_draft(project_id: str, draft_id: str, settings=Depends(get_app_settings)) -> SceneDraftDetailResponse:
    service = _get_service(settings)
    try:
        draft = service.reject(project_id, draft_id)
        bundle = service.get_context_bundle_for_draft(project_id, draft_id)
        return SceneDraftDetailResponse(draft=draft, context_bundle=bundle)
    except Exception as error:
        raise _map_error(error) from error
