from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from backend.app.core.dependencies import get_app_paths, get_app_settings, get_bible_service, get_file_repository, get_sqlite_repository
from backend.app.domain.models.project import CharacterDocument, PowerSystemDocument, StoryBible, WorldDocument
from backend.app.schemas.bible import (
    BibleAggregateResponse,
    CharacterCreateRequest,
    CharacterUpdateRequest,
    PowerSystemWriteRequest,
    StoryBibleWriteRequest,
    WorldWriteRequest,
)
from backend.app.services.bible_service import BibleService
from backend.app.services.exceptions import ConflictError

router = APIRouter(prefix="/api/projects/{project_id}", tags=["bible"])


def _get_service(settings) -> BibleService:
    paths = get_app_paths(settings)
    return get_bible_service(paths, get_file_repository(), get_sqlite_repository(paths))


def _map_error(error: Exception) -> HTTPException:
    if isinstance(error, KeyError):
        return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project or resource not found")
    if isinstance(error, ConflictError):
        return HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error))
    if isinstance(error, ValueError):
        return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(error))
    raise error


@router.get("/bible", response_model=BibleAggregateResponse)
def get_bible(project_id: str, settings=Depends(get_app_settings)) -> BibleAggregateResponse:
    service = _get_service(settings)
    try:
        return service.get_bible_aggregate(project_id)
    except Exception as error:
        raise _map_error(error) from error


@router.post("/bible/from-consultant", response_model=BibleAggregateResponse, status_code=status.HTTP_201_CREATED)
def initialize_bible_from_consultant(project_id: str, settings=Depends(get_app_settings)) -> BibleAggregateResponse:
    service = _get_service(settings)
    try:
        return service.initialize_from_consultant(project_id)
    except Exception as error:
        raise _map_error(error) from error


@router.get("/bible/story-bible", response_model=StoryBible)
def get_story_bible(project_id: str, settings=Depends(get_app_settings)) -> StoryBible:
    service = _get_service(settings)
    try:
        return service.get_bible_aggregate(project_id).story_bible
    except Exception as error:
        raise _map_error(error) from error


@router.put("/bible/story-bible", response_model=StoryBible)
def put_story_bible(project_id: str, request: StoryBibleWriteRequest, settings=Depends(get_app_settings)) -> StoryBible:
    service = _get_service(settings)
    try:
        return service.update_story_bible(project_id, request.model_dump(mode="python", exclude_none=True), partial=False)
    except Exception as error:
        raise _map_error(error) from error


@router.patch("/bible/story-bible", response_model=StoryBible)
def patch_story_bible(project_id: str, request: StoryBibleWriteRequest, settings=Depends(get_app_settings)) -> StoryBible:
    service = _get_service(settings)
    try:
        return service.update_story_bible(project_id, request.model_dump(mode="python", exclude_none=True), partial=True)
    except Exception as error:
        raise _map_error(error) from error


@router.post("/bible/story-bible/confirm", response_model=StoryBible)
def confirm_story_bible(project_id: str, settings=Depends(get_app_settings)) -> StoryBible:
    service = _get_service(settings)
    try:
        return service.confirm_story_bible(project_id)
    except Exception as error:
        raise _map_error(error) from error


@router.get("/bible/world", response_model=WorldDocument)
def get_world(project_id: str, settings=Depends(get_app_settings)) -> WorldDocument:
    service = _get_service(settings)
    try:
        return service.get_bible_aggregate(project_id).world
    except Exception as error:
        raise _map_error(error) from error


@router.put("/bible/world", response_model=WorldDocument)
def put_world(project_id: str, request: WorldWriteRequest, settings=Depends(get_app_settings)) -> WorldDocument:
    service = _get_service(settings)
    try:
        return service.update_world(project_id, request.model_dump(mode="python", exclude_none=True), partial=False)
    except Exception as error:
        raise _map_error(error) from error


@router.patch("/bible/world", response_model=WorldDocument)
def patch_world(project_id: str, request: WorldWriteRequest, settings=Depends(get_app_settings)) -> WorldDocument:
    service = _get_service(settings)
    try:
        return service.update_world(project_id, request.model_dump(mode="python", exclude_none=True), partial=True)
    except Exception as error:
        raise _map_error(error) from error


@router.post("/bible/world/confirm", response_model=WorldDocument)
def confirm_world(project_id: str, settings=Depends(get_app_settings)) -> WorldDocument:
    service = _get_service(settings)
    try:
        return service.confirm_world(project_id)
    except Exception as error:
        raise _map_error(error) from error


@router.get("/bible/power-system", response_model=PowerSystemDocument)
def get_power_system(project_id: str, settings=Depends(get_app_settings)) -> PowerSystemDocument:
    service = _get_service(settings)
    try:
        return service.get_bible_aggregate(project_id).power_system
    except Exception as error:
        raise _map_error(error) from error


@router.put("/bible/power-system", response_model=PowerSystemDocument)
def put_power_system(project_id: str, request: PowerSystemWriteRequest, settings=Depends(get_app_settings)) -> PowerSystemDocument:
    service = _get_service(settings)
    try:
        return service.update_power_system(project_id, request.model_dump(mode="python", exclude_none=True), partial=False)
    except Exception as error:
        raise _map_error(error) from error


@router.patch("/bible/power-system", response_model=PowerSystemDocument)
def patch_power_system(project_id: str, request: PowerSystemWriteRequest, settings=Depends(get_app_settings)) -> PowerSystemDocument:
    service = _get_service(settings)
    try:
        return service.update_power_system(project_id, request.model_dump(mode="python", exclude_none=True), partial=True)
    except Exception as error:
        raise _map_error(error) from error


@router.post("/bible/power-system/confirm", response_model=PowerSystemDocument)
def confirm_power_system(project_id: str, settings=Depends(get_app_settings)) -> PowerSystemDocument:
    service = _get_service(settings)
    try:
        return service.confirm_power_system(project_id)
    except Exception as error:
        raise _map_error(error) from error


@router.get("/characters", response_model=CharacterDocument)
def get_characters(project_id: str, settings=Depends(get_app_settings)) -> CharacterDocument:
    service = _get_service(settings)
    try:
        return service.get_bible_aggregate(project_id).characters
    except Exception as error:
        raise _map_error(error) from error


@router.post("/characters", status_code=status.HTTP_201_CREATED)
def create_character(project_id: str, request: CharacterCreateRequest, settings=Depends(get_app_settings)):
    service = _get_service(settings)
    try:
        return service.create_character(project_id, request.model_dump(mode="python"))
    except Exception as error:
        raise _map_error(error) from error


@router.get("/characters/{character_id}")
def get_character(project_id: str, character_id: str, settings=Depends(get_app_settings)):
    service = _get_service(settings)
    try:
        return service.get_character(project_id, character_id)
    except Exception as error:
        raise _map_error(error) from error


@router.put("/characters/{character_id}")
def put_character(project_id: str, character_id: str, request: CharacterCreateRequest, settings=Depends(get_app_settings)):
    service = _get_service(settings)
    try:
        return service.update_character(project_id, character_id, request.model_dump(mode="python"))
    except Exception as error:
        raise _map_error(error) from error


@router.patch("/characters/{character_id}")
def patch_character(project_id: str, character_id: str, request: CharacterUpdateRequest, settings=Depends(get_app_settings)):
    service = _get_service(settings)
    try:
        return service.update_character(project_id, character_id, request.model_dump(mode="python", exclude_none=True))
    except Exception as error:
        raise _map_error(error) from error


@router.delete("/characters/{character_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_character(project_id: str, character_id: str, settings=Depends(get_app_settings)) -> None:
    service = _get_service(settings)
    try:
        service.delete_character(project_id, character_id)
    except Exception as error:
        raise _map_error(error) from error


@router.post("/characters/confirm", response_model=CharacterDocument)
def confirm_characters(project_id: str, settings=Depends(get_app_settings)) -> CharacterDocument:
    service = _get_service(settings)
    try:
        return service.confirm_characters(project_id)
    except Exception as error:
        raise _map_error(error) from error
