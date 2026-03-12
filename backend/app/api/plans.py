from __future__ import annotations

from fastapi import APIRouter, Body, Depends, HTTPException, status

from backend.app.core.dependencies import (
    get_app_paths,
    get_app_settings,
    get_bible_service,
    get_file_repository,
    get_planner_service,
    get_sqlite_repository,
)
from backend.app.domain.models.planning import ChapterPlan, MasterOutlineDocument, ScenePlan, VolumePlan
from backend.app.schemas.plans import (
    ChapterListResponse,
    ChapterWriteRequest,
    PlanGenerateOptions,
    SceneListResponse,
    SceneWriteRequest,
    VolumeListResponse,
    VolumeWriteRequest,
)
from backend.app.services.exceptions import ConflictError

router = APIRouter(prefix="/api/projects/{project_id}/plans", tags=["plans"])


def _get_service(settings):
    paths = get_app_paths(settings)
    file_repository = get_file_repository()
    sqlite_repository = get_sqlite_repository(paths)
    bible_service = get_bible_service(paths, file_repository, sqlite_repository)
    return get_planner_service(paths, file_repository, sqlite_repository, bible_service)


def _map_error(error: Exception) -> HTTPException:
    if isinstance(error, KeyError):
        return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project or resource not found")
    if isinstance(error, ConflictError):
        return HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error))
    if isinstance(error, ValueError):
        return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(error))
    raise error


@router.get("/master-outline", response_model=MasterOutlineDocument)
def get_master_outline(project_id: str, settings=Depends(get_app_settings)) -> MasterOutlineDocument:
    service = _get_service(settings)
    try:
        return service.get_master_outline(project_id)
    except Exception as error:
        raise _map_error(error) from error


@router.post("/master-outline/confirm", response_model=MasterOutlineDocument)
def confirm_master_outline(project_id: str, settings=Depends(get_app_settings)) -> MasterOutlineDocument:
    service = _get_service(settings)
    try:
        return service.confirm_master_outline(project_id)
    except Exception as error:
        raise _map_error(error) from error


@router.post("/volumes/generate", response_model=MasterOutlineDocument, status_code=status.HTTP_201_CREATED)
def generate_volumes(
    project_id: str,
    request: PlanGenerateOptions | None = Body(default=None),
    settings=Depends(get_app_settings),
) -> MasterOutlineDocument:
    service = _get_service(settings)
    request = request or PlanGenerateOptions()
    try:
        return service.generate_volumes(
            project_id,
            overwrite=request.overwrite,
            volume_count_hint=request.volume_count_hint,
            chapters_per_volume_hint=request.chapters_per_volume_hint,
        )
    except Exception as error:
        raise _map_error(error) from error


@router.get("/volumes", response_model=VolumeListResponse)
def list_volumes(project_id: str, settings=Depends(get_app_settings)) -> VolumeListResponse:
    service = _get_service(settings)
    try:
        return VolumeListResponse(items=service.list_volumes(project_id))
    except Exception as error:
        raise _map_error(error) from error


@router.get("/volumes/{volume_id}", response_model=VolumePlan)
def get_volume(project_id: str, volume_id: str, settings=Depends(get_app_settings)) -> VolumePlan:
    service = _get_service(settings)
    try:
        return service.get_volume(project_id, volume_id)
    except Exception as error:
        raise _map_error(error) from error


@router.put("/volumes/{volume_id}", response_model=VolumePlan)
def put_volume(project_id: str, volume_id: str, request: VolumeWriteRequest, settings=Depends(get_app_settings)) -> VolumePlan:
    service = _get_service(settings)
    try:
        return service.update_volume(project_id, volume_id, request.model_dump(mode="python", exclude_none=True))
    except Exception as error:
        raise _map_error(error) from error


@router.patch("/volumes/{volume_id}", response_model=VolumePlan)
def patch_volume(project_id: str, volume_id: str, request: VolumeWriteRequest, settings=Depends(get_app_settings)) -> VolumePlan:
    service = _get_service(settings)
    try:
        return service.update_volume(project_id, volume_id, request.model_dump(mode="python", exclude_none=True))
    except Exception as error:
        raise _map_error(error) from error


@router.post("/volumes/{volume_id}/confirm", response_model=VolumePlan)
def confirm_volume(project_id: str, volume_id: str, settings=Depends(get_app_settings)) -> VolumePlan:
    service = _get_service(settings)
    try:
        return service.confirm_volume(project_id, volume_id)
    except Exception as error:
        raise _map_error(error) from error


@router.post("/volumes/{volume_id}/chapters/generate", response_model=ChapterListResponse, status_code=status.HTTP_201_CREATED)
def generate_chapters(
    project_id: str,
    volume_id: str,
    request: PlanGenerateOptions | None = Body(default=None),
    settings=Depends(get_app_settings),
) -> ChapterListResponse:
    service = _get_service(settings)
    request = request or PlanGenerateOptions()
    try:
        return ChapterListResponse(items=service.generate_chapters(project_id, volume_id, overwrite=request.overwrite))
    except Exception as error:
        raise _map_error(error) from error


@router.get("/volumes/{volume_id}/chapters", response_model=ChapterListResponse)
def list_chapters(project_id: str, volume_id: str, settings=Depends(get_app_settings)) -> ChapterListResponse:
    service = _get_service(settings)
    try:
        return ChapterListResponse(items=service.list_chapters(project_id, volume_id))
    except Exception as error:
        raise _map_error(error) from error


@router.get("/chapters/{chapter_id}", response_model=ChapterPlan)
def get_chapter(project_id: str, chapter_id: str, settings=Depends(get_app_settings)) -> ChapterPlan:
    service = _get_service(settings)
    try:
        return service.get_chapter(project_id, chapter_id)
    except Exception as error:
        raise _map_error(error) from error


@router.put("/chapters/{chapter_id}", response_model=ChapterPlan)
def put_chapter(project_id: str, chapter_id: str, request: ChapterWriteRequest, settings=Depends(get_app_settings)) -> ChapterPlan:
    service = _get_service(settings)
    try:
        return service.update_chapter(project_id, chapter_id, request.model_dump(mode="python", exclude_none=True))
    except Exception as error:
        raise _map_error(error) from error


@router.patch("/chapters/{chapter_id}", response_model=ChapterPlan)
def patch_chapter(project_id: str, chapter_id: str, request: ChapterWriteRequest, settings=Depends(get_app_settings)) -> ChapterPlan:
    service = _get_service(settings)
    try:
        return service.update_chapter(project_id, chapter_id, request.model_dump(mode="python", exclude_none=True))
    except Exception as error:
        raise _map_error(error) from error


@router.post("/chapters/{chapter_id}/confirm", response_model=ChapterPlan)
def confirm_chapter(project_id: str, chapter_id: str, settings=Depends(get_app_settings)) -> ChapterPlan:
    service = _get_service(settings)
    try:
        return service.confirm_chapter(project_id, chapter_id)
    except Exception as error:
        raise _map_error(error) from error


@router.post("/chapters/{chapter_id}/scenes/generate", response_model=SceneListResponse, status_code=status.HTTP_201_CREATED)
def generate_scenes(
    project_id: str,
    chapter_id: str,
    request: PlanGenerateOptions | None = Body(default=None),
    settings=Depends(get_app_settings),
) -> SceneListResponse:
    service = _get_service(settings)
    request = request or PlanGenerateOptions()
    try:
        return SceneListResponse(
            items=service.generate_scenes(project_id, chapter_id, overwrite=request.overwrite, scene_count_hint=request.scene_count_hint)
        )
    except Exception as error:
        raise _map_error(error) from error


@router.get("/chapters/{chapter_id}/scenes", response_model=SceneListResponse)
def list_scenes(project_id: str, chapter_id: str, settings=Depends(get_app_settings)) -> SceneListResponse:
    service = _get_service(settings)
    try:
        return SceneListResponse(items=service.list_scenes(project_id, chapter_id))
    except Exception as error:
        raise _map_error(error) from error


@router.get("/scenes/{scene_id}", response_model=ScenePlan)
def get_scene(project_id: str, scene_id: str, settings=Depends(get_app_settings)) -> ScenePlan:
    service = _get_service(settings)
    try:
        return service.get_scene(project_id, scene_id)
    except Exception as error:
        raise _map_error(error) from error


@router.put("/scenes/{scene_id}", response_model=ScenePlan)
def put_scene(project_id: str, scene_id: str, request: SceneWriteRequest, settings=Depends(get_app_settings)) -> ScenePlan:
    service = _get_service(settings)
    try:
        return service.update_scene(project_id, scene_id, request.model_dump(mode="python", exclude_none=True))
    except Exception as error:
        raise _map_error(error) from error


@router.patch("/scenes/{scene_id}", response_model=ScenePlan)
def patch_scene(project_id: str, scene_id: str, request: SceneWriteRequest, settings=Depends(get_app_settings)) -> ScenePlan:
    service = _get_service(settings)
    try:
        return service.update_scene(project_id, scene_id, request.model_dump(mode="python", exclude_none=True))
    except Exception as error:
        raise _map_error(error) from error


@router.post("/scenes/{scene_id}/confirm", response_model=ScenePlan)
def confirm_scene(project_id: str, scene_id: str, settings=Depends(get_app_settings)) -> ScenePlan:
    service = _get_service(settings)
    try:
        return service.confirm_scene(project_id, scene_id)
    except Exception as error:
        raise _map_error(error) from error
