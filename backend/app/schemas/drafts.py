from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict

from backend.app.domain.models.issues import SceneDraftCheckReport
from backend.app.domain.models.writing import ContextBundle, SceneDraft, SceneDraftManifest


class GenerateSceneDraftRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    mode: Literal["outline_strict", "momentum"] = "outline_strict"


class SceneDraftDetailResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    draft: SceneDraft
    context_bundle: ContextBundle | None = None
    check_report: SceneDraftCheckReport | None = None


class SceneDraftManifestResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    manifest: SceneDraftManifest
