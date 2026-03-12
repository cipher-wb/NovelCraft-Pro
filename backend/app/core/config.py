from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict


class Settings(BaseModel):
    model_config = ConfigDict(frozen=True)

    app_name: str = "novelcraft-pro"
    app_env: str = "development"
    app_host: str = "127.0.0.1"
    app_port: int = 8000
    data_root: Path
    projects_root: Path
    llm_mode: Literal["mock", "openai"] = "mock"
    openai_base_url: str = "https://api.openai.com/v1"
    openai_api_key: str = ""

    @classmethod
    def from_env(cls) -> "Settings":
        cwd = Path.cwd()

        def resolve_path(name: str, default: str) -> Path:
            raw = os.getenv(name, default)
            path = Path(raw)
            return path if path.is_absolute() else (cwd / path).resolve()

        return cls(
            app_name=os.getenv("APP_NAME", "novelcraft-pro"),
            app_env=os.getenv("APP_ENV", "development"),
            app_host=os.getenv("APP_HOST", "127.0.0.1"),
            app_port=int(os.getenv("APP_PORT", "8000")),
            data_root=resolve_path("DATA_ROOT", "./data"),
            projects_root=resolve_path("PROJECTS_ROOT", "./projects"),
            llm_mode=os.getenv("LLM_MODE", "mock"),
            openai_base_url=os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1"),
            openai_api_key=os.getenv("OPENAI_API_KEY", ""),
        )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings.from_env()


def reset_settings_cache() -> None:
    get_settings.cache_clear()
