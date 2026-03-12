from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from backend.app.domain.models.issues import SceneDraftCheckReport


class DraftCheckReportResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    report: SceneDraftCheckReport
