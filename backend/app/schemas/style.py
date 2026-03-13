from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from backend.app.domain.models.style import VoiceProfileDocument


class VoiceProfileResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    profile: VoiceProfileDocument
    warnings: list[str] = Field(default_factory=list)

