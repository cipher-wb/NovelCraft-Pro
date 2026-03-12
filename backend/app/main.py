from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from backend.app.api.router import router as api_router
from backend.app.core.config import reset_settings_cache
from backend.app.core.dependencies import get_app_paths, get_app_settings, get_sqlite_repository


def create_app() -> FastAPI:
    reset_settings_cache()
    settings = get_app_settings()
    paths = get_app_paths(settings)
    paths.ensure_runtime_dirs()

    sqlite_repository = get_sqlite_repository(paths)
    sqlite_repository.initialize()

    app = FastAPI(title="NovelCraft Pro", version="0.1.0")
    app.include_router(api_router)

    studio_dir = Path(__file__).resolve().parent / "static" / "studio"
    app.mount("/studio", StaticFiles(directory=studio_dir, html=True), name="studio")
    return app


app = create_app()
