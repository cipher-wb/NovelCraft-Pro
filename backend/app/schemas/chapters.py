from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from backend.app.domain.models.issues import ChapterCheckReport
from backend.app.domain.models.writing import ChapterAssembledDocument


class ChapterAssemblyDetailResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    assembled: ChapterAssembledDocument
    check_report: ChapterCheckReport | None = None


class ChapterCheckReportResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    report: ChapterCheckReport
