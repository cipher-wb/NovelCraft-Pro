from __future__ import annotations

from fastapi import APIRouter, Body, Depends, HTTPException, status
from pydantic import ValidationError

from backend.app.core.dependencies import get_app_paths, get_app_settings, get_file_repository, get_sqlite_repository, get_style_service
from backend.app.schemas.style import VoiceProfileResponse
from backend.app.services.exceptions import ConflictError

router = APIRouter(prefix="/api/projects/{project_id}/style", tags=["style"])


def _get_service(settings):
    paths = get_app_paths(settings)
    return get_style_service(paths, get_file_repository(), get_sqlite_repository(paths))


def _map_error(error: Exception) -> HTTPException:
    if isinstance(error, KeyError):
        return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project or resource not found")
    if isinstance(error, ConflictError):
        return HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error))
    if isinstance(error, (ValueError, ValidationError)):
        return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(error))
    raise error


@router.get("/voice-profile", response_model=VoiceProfileResponse)
def get_voice_profile(project_id: str, settings=Depends(get_app_settings)) -> VoiceProfileResponse:
    service = _get_service(settings)
    try:
        result = service.get_voice_profile(project_id)
        return VoiceProfileResponse(profile=result.profile, warnings=result.warnings)
    except Exception as error:
        raise _map_error(error) from error


@router.put("/voice-profile", response_model=VoiceProfileResponse)
def put_voice_profile(
    project_id: str,
    request: dict = Body(...),
    settings=Depends(get_app_settings),
) -> VoiceProfileResponse:
    service = _get_service(settings)
    try:
        profile = service.put_voice_profile(project_id, request)
        return VoiceProfileResponse(profile=profile, warnings=[])
    except Exception as error:
        raise _map_error(error) from error
