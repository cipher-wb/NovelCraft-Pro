from __future__ import annotations

from backend.app.core.config import Settings, get_settings
from backend.app.core.paths import AppPaths
from backend.app.repositories.file_repository import FileRepository
from backend.app.repositories.sqlite_repository import SQLiteRepository
from backend.app.repositories.vector_repository import VectorRepository
from backend.app.services.bootstrap_service import BootstrapService
from backend.app.services.consultant_service import ConsultantService
from backend.app.services.project_service import ProjectService


def get_app_settings() -> Settings:
    return get_settings()


def get_app_paths(settings: Settings) -> AppPaths:
    return AppPaths(settings)


def get_file_repository() -> FileRepository:
    return FileRepository()


def get_sqlite_repository(paths: AppPaths) -> SQLiteRepository:
    return SQLiteRepository(paths.app_db_path)


def get_vector_repository(paths: AppPaths) -> VectorRepository:
    return VectorRepository(paths.data_root / "vectorstore_stub")


def get_bootstrap_service(paths: AppPaths, file_repository: FileRepository) -> BootstrapService:
    return BootstrapService(paths, file_repository)


def get_project_service(
    paths: AppPaths,
    file_repository: FileRepository,
    sqlite_repository: SQLiteRepository,
    vector_repository: VectorRepository,
    bootstrap_service: BootstrapService,
) -> ProjectService:
    return ProjectService(paths, file_repository, sqlite_repository, vector_repository, bootstrap_service)


def get_consultant_service(
    paths: AppPaths,
    file_repository: FileRepository,
    sqlite_repository: SQLiteRepository,
) -> ConsultantService:
    return ConsultantService(paths, file_repository, sqlite_repository)
