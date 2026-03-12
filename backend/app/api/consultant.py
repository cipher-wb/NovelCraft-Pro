from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from backend.app.core.dependencies import get_app_paths, get_app_settings, get_consultant_service, get_file_repository, get_sqlite_repository
from backend.app.schemas.consultant import (
    ConsultantAnswerRequest,
    ConsultantFinalizeResponse,
    ConsultantSessionStartRequest,
    ConsultantSessionState,
)

router = APIRouter(tags=["consultant"])


@router.post(
    "/api/projects/{project_id}/consultant/sessions",
    response_model=ConsultantSessionState,
    status_code=status.HTTP_201_CREATED,
)
def start_session(project_id: str, request: ConsultantSessionStartRequest, settings=Depends(get_app_settings)) -> ConsultantSessionState:
    service = get_consultant_service(
        get_app_paths(settings),
        get_file_repository(),
        get_sqlite_repository(get_app_paths(settings)),
    )
    try:
        return service.start_session(project_id, request.brief, request.preferred_subgenres, request.constraints)
    except KeyError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found") from error


@router.post("/api/consultant/sessions/{session_id}/answer", response_model=ConsultantSessionState)
def answer_session(session_id: str, request: ConsultantAnswerRequest, settings=Depends(get_app_settings)) -> ConsultantSessionState:
    service = get_consultant_service(
        get_app_paths(settings),
        get_file_repository(),
        get_sqlite_repository(get_app_paths(settings)),
    )
    try:
        return service.answer_session(session_id, request.question_id, request.answer)
    except KeyError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found") from error
    except ValueError as error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(error)) from error


@router.post("/api/consultant/sessions/{session_id}/finalize", response_model=ConsultantFinalizeResponse)
def finalize_session(session_id: str, settings=Depends(get_app_settings)) -> ConsultantFinalizeResponse:
    service = get_consultant_service(
        get_app_paths(settings),
        get_file_repository(),
        get_sqlite_repository(get_app_paths(settings)),
    )
    try:
        dossier, dossier_path = service.finalize_session(session_id)
    except KeyError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session or project not found") from error
    except ValueError as error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(error)) from error
    return ConsultantFinalizeResponse(
        session_id=session_id,
        status="completed",
        dossier_path=dossier_path,
        dossier=dossier,
    )
