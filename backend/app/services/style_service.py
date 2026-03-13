from __future__ import annotations

import json
import re
from pathlib import Path

from pydantic import ValidationError

from backend.app.core.paths import AppPaths
from backend.app.domain.models.common import utc_now
from backend.app.domain.models.style import (
    StyleConstraintBundle,
    StyleGlobalConstraintsBundle,
    VoiceProfileDocument,
    VoiceProfileReadResult,
)
from backend.app.repositories.file_repository import FileRepository
from backend.app.repositories.sqlite_repository import SQLiteRepository

_WHITESPACE_RE = re.compile(r"\s+")
_MULTI_BLANK_RE = re.compile(r"\n{3,}")


class StyleService:
    def __init__(self, paths: AppPaths, file_repository: FileRepository, sqlite_repository: SQLiteRepository) -> None:
        self.paths = paths
        self.file_repository = file_repository
        self.sqlite_repository = sqlite_repository

    def get_voice_profile(self, project_id: str) -> VoiceProfileReadResult:
        project = self._require_project(project_id)
        path = self.paths.voice_profile_path(project["slug"])
        if not self.file_repository.exists(path):
            return VoiceProfileReadResult(profile=self._disabled_profile(project_id))
        try:
            raw = self.file_repository.read_text(path).strip()
            if raw == "" or raw == "{}":
                return VoiceProfileReadResult(profile=self._disabled_profile(project_id))
            payload = json.loads(raw)
            profile = VoiceProfileDocument.model_validate(payload)
            return VoiceProfileReadResult(profile=profile)
        except (json.JSONDecodeError, ValidationError, TypeError, ValueError) as error:
            return VoiceProfileReadResult(
                profile=self._disabled_profile(project_id),
                warnings=[f"voice_profile.json is invalid and has been disabled: {error.__class__.__name__}"],
            )

    def put_voice_profile(self, project_id: str, payload: dict) -> VoiceProfileDocument:
        project = self._require_project(project_id)
        if payload.get("project_id") != project_id:
            raise ValueError("project_id must match the target project.")
        profile = VoiceProfileDocument.model_validate(payload)
        path = self.paths.voice_profile_path(project["slug"])
        self.file_repository.write_json(path, profile.model_dump(mode="json"))
        return profile

    def disabled_bundle(self, warnings: list[str] | None = None) -> StyleConstraintBundle:
        return StyleConstraintBundle(
            enabled=False,
            profile_name="",
            global_constraints=StyleGlobalConstraintsBundle(),
            character_voice_briefs=[],
            warnings=list(warnings or []),
        )

    def sanitize_text(
        self,
        content_md: str,
        summary: str,
        style_bundle: StyleConstraintBundle,
        protected_phrases: set[str] | None = None,
    ) -> tuple[str, str]:
        protected = {phrase for phrase in (protected_phrases or set()) if phrase}
        content = self._normalize_block(content_md)
        short_summary = self._normalize_block(summary)
        if not style_bundle.enabled:
            return content, short_summary

        replacements = {}
        masked_content = content
        masked_summary = short_summary
        for index, phrase in enumerate(sorted(protected, key=lambda value: (-len(value), value))):
            placeholder = f"__NC_STYLE_PROTECTED_{index}__"
            replacements[placeholder] = phrase
            masked_content = masked_content.replace(phrase, placeholder)
            masked_summary = masked_summary.replace(phrase, placeholder)

        removal_phrases = list(style_bundle.global_constraints.banned_phrases)
        for brief in style_bundle.character_voice_briefs:
            removal_phrases.extend(brief.forbidden_terms)
        for phrase in sorted({item for item in removal_phrases if item}, key=lambda value: (-len(value), value)):
            masked_content = masked_content.replace(phrase, "")
            masked_summary = masked_summary.replace(phrase, "")

        masked_content = self._normalize_block(masked_content)
        masked_summary = self._normalize_block(masked_summary)

        for placeholder, phrase in replacements.items():
            masked_content = masked_content.replace(placeholder, phrase)
            masked_summary = masked_summary.replace(placeholder, phrase)

        return self._normalize_block(masked_content), self._normalize_block(masked_summary)

    def _normalize_block(self, text: str) -> str:
        normalized = text.replace("\r\n", "\n").replace("\r", "\n")
        lines = [line.rstrip() for line in normalized.split("\n")]
        normalized = "\n".join(lines).strip()
        normalized = _MULTI_BLANK_RE.sub("\n\n", normalized)
        return normalized

    def _disabled_profile(self, project_id: str) -> VoiceProfileDocument:
        return VoiceProfileDocument(
            project_id=project_id,
            version=1,
            updated_at=utc_now(),
            enabled=False,
            profile_name="",
        )

    def _require_project(self, project_id: str) -> dict:
        project = self.sqlite_repository.get_project_record(project_id)
        if project is None:
            raise KeyError(project_id)
        return project

