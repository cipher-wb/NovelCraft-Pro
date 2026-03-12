from __future__ import annotations

from fastapi import APIRouter, Depends

from backend.app.core.config import Settings
from backend.app.core.dependencies import get_app_settings

router = APIRouter()


@router.get("/health")
def health(settings: Settings = Depends(get_app_settings)) -> dict[str, str]:
    return {"status": "ok", "app": settings.app_name, "mode": settings.llm_mode}
