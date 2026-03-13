from __future__ import annotations

from backend.app.core.config import Settings, get_settings
from backend.app.core.paths import AppPaths
from backend.app.infra.llm_gateway import MockLLMGateway, OpenAICompatibleGateway
from backend.app.repositories.file_repository import FileRepository
from backend.app.repositories.sqlite_repository import SQLiteRepository
from backend.app.repositories.vector_repository import VectorRepository
from backend.app.services.bible_service import BibleService
from backend.app.services.bootstrap_service import BootstrapService
from backend.app.services.checks_service import ChecksService
from backend.app.services.consultant_service import ConsultantService
from backend.app.services.context_bundle_service import ContextBundleService
from backend.app.services.memory_service import MemoryService
from backend.app.services.planner_service import PlannerService
from backend.app.services.project_service import ProjectService
from backend.app.services.repair_service import RepairService
from backend.app.services.retrieval_service import RetrievalService
from backend.app.services.scene_draft_service import SceneDraftService


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



def get_llm_gateway(settings: Settings):
    if settings.llm_mode == "mock":
        return MockLLMGateway()
    return OpenAICompatibleGateway(
        base_url=settings.openai_base_url,
        api_key=settings.openai_api_key,
    )



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



def get_bible_service(
    paths: AppPaths,
    file_repository: FileRepository,
    sqlite_repository: SQLiteRepository,
) -> BibleService:
    return BibleService(paths, file_repository, sqlite_repository)



def get_planner_service(
    paths: AppPaths,
    file_repository: FileRepository,
    sqlite_repository: SQLiteRepository,
    bible_service: BibleService,
) -> PlannerService:
    return PlannerService(paths, file_repository, sqlite_repository, bible_service)



def get_memory_service(paths: AppPaths, file_repository: FileRepository, bible_service: BibleService) -> MemoryService:
    return MemoryService(paths, file_repository, bible_service)



def get_retrieval_service(
    paths: AppPaths,
    file_repository: FileRepository,
    sqlite_repository: SQLiteRepository,
    planner_service: PlannerService,
) -> RetrievalService:
    return RetrievalService(paths, file_repository, sqlite_repository, planner_service)



def get_context_bundle_service(
    paths: AppPaths,
    file_repository: FileRepository,
    bible_service: BibleService,
    planner_service: PlannerService,
    retrieval_service: RetrievalService,
) -> ContextBundleService:
    return ContextBundleService(paths, file_repository, bible_service, planner_service, retrieval_service)



def get_checks_service(
    paths: AppPaths,
    file_repository: FileRepository,
    sqlite_repository: SQLiteRepository,
    bible_service: BibleService,
    planner_service: PlannerService,
    context_bundle_service: ContextBundleService,
) -> ChecksService:
    return ChecksService(paths, file_repository, sqlite_repository, bible_service, planner_service, context_bundle_service)



def get_scene_draft_service(
    paths: AppPaths,
    file_repository: FileRepository,
    sqlite_repository: SQLiteRepository,
    bible_service: BibleService,
    planner_service: PlannerService,
    context_bundle_service: ContextBundleService,
    memory_service: MemoryService,
    checks_service: ChecksService,
    llm_gateway,
) -> SceneDraftService:
    return SceneDraftService(
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



def get_repair_service(
    paths: AppPaths,
    file_repository: FileRepository,
    sqlite_repository: SQLiteRepository,
    planner_service: PlannerService,
    scene_draft_service: SceneDraftService,
    context_bundle_service: ContextBundleService,
    checks_service: ChecksService,
    llm_gateway,
) -> RepairService:
    return RepairService(
        paths,
        file_repository,
        sqlite_repository,
        planner_service,
        scene_draft_service,
        context_bundle_service,
        checks_service,
        llm_gateway,
    )
