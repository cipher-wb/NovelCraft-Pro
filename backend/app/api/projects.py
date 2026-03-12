from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from backend.app.core.dependencies import (
    get_app_paths,
    get_app_settings,
    get_bootstrap_service,
    get_file_repository,
    get_project_service,
    get_sqlite_repository,
    get_vector_repository,
)
from backend.app.schemas.project import (
    CreateProjectRequest,
    CreateProjectResponse,
    ProjectDetailResponse,
    ProjectListResponse,
)
from backend.app.services.project_service import ProjectService

router = APIRouter(prefix="/api/projects", tags=["projects"])


@router.post("", response_model=CreateProjectResponse, status_code=status.HTTP_201_CREATED)
def create_project(
    request: CreateProjectRequest,
    settings=Depends(get_app_settings),
) -> CreateProjectResponse:
    service = get_project_service(
        get_app_paths(settings),
        get_file_repository(),
        get_sqlite_repository(get_app_paths(settings)),
        get_vector_repository(get_app_paths(settings)),
        get_bootstrap_service(get_app_paths(settings), get_file_repository()),
    )
    manifest, _ = service.create_project(request)
    return CreateProjectResponse(project_id=manifest.project_id, slug=manifest.slug, manifest=manifest)


@router.get("", response_model=ProjectListResponse)
def list_projects(settings=Depends(get_app_settings)) -> ProjectListResponse:
    service = get_project_service(
        get_app_paths(settings),
        get_file_repository(),
        get_sqlite_repository(get_app_paths(settings)),
        get_vector_repository(get_app_paths(settings)),
        get_bootstrap_service(get_app_paths(settings), get_file_repository()),
    )
    return ProjectListResponse(items=service.list_projects())


@router.get("/{project_id}", response_model=ProjectDetailResponse)
def get_project(project_id: str, settings=Depends(get_app_settings)) -> ProjectDetailResponse:
    service = get_project_service(
        get_app_paths(settings),
        get_file_repository(),
        get_sqlite_repository(get_app_paths(settings)),
        get_vector_repository(get_app_paths(settings)),
        get_bootstrap_service(get_app_paths(settings), get_file_repository()),
    )
    try:
        manifest = service.get_project(project_id)
        paths = service.get_project_paths(project_id)
    except KeyError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found") from error
    return ProjectDetailResponse(manifest=manifest, paths=paths)
