from __future__ import annotations

from fastapi import APIRouter

from backend.app.api.bible import router as bible_router
from backend.app.api.consultant import router as consultant_router
from backend.app.api.drafts import router as drafts_router
from backend.app.api.health import router as health_router
from backend.app.api.plans import router as plans_router
from backend.app.api.projects import router as projects_router
from backend.app.api.style import router as style_router

router = APIRouter()
router.include_router(health_router)
router.include_router(projects_router)
router.include_router(consultant_router)
router.include_router(bible_router)
router.include_router(style_router)
router.include_router(plans_router)
router.include_router(drafts_router)
