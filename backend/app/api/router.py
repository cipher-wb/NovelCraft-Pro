from __future__ import annotations

from fastapi import APIRouter

from backend.app.api.consultant import router as consultant_router
from backend.app.api.health import router as health_router
from backend.app.api.projects import router as projects_router

router = APIRouter()
router.include_router(health_router)
router.include_router(projects_router)
router.include_router(consultant_router)
