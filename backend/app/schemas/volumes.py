from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from backend.app.domain.models.issues import VolumeCheckReport
from backend.app.domain.models.writing import VolumeAssembledDocument


class VolumeAssemblyDetailResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    assembled: VolumeAssembledDocument
    check_report: VolumeCheckReport | None = None


class VolumeCheckReportResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    report: VolumeCheckReport
