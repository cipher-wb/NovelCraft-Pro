from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from backend.app.domain.models.project import ConsultantDossier


class QuestionPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    question_id: str
    prompt: str


class ConsultantSessionStartRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    brief: str = Field(min_length=1)
    preferred_subgenres: list[str] = Field(default_factory=list)
    constraints: list[str] = Field(default_factory=list)


class ConsultantSessionState(BaseModel):
    model_config = ConfigDict(extra="forbid")

    session_id: str
    project_id: str
    status: str
    current_question: QuestionPayload | None
    answered_count: int
    total_questions: int
    ready_to_finalize: bool


class ConsultantAnswerRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    question_id: str
    answer: str = Field(min_length=1)


class ConsultantFinalizeResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    session_id: str
    status: str
    dossier_path: str
    dossier: ConsultantDossier


class ConsultantTranscriptItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    question_id: str
    prompt: str
    answer: str


class ConsultantSessionDebugState(BaseModel):
    model_config = ConfigDict(extra="forbid")

    answers: dict[str, str]
    transcript: list[dict[str, Any]]
