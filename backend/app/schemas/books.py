from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from backend.app.domain.models.issues import BookCheckReport
from backend.app.domain.models.writing import BookAssembledDocument


class BookAssemblyDetailResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    assembled: BookAssembledDocument
    check_report: BookCheckReport | None = None


class BookCheckReportResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    report: BookCheckReport
