from __future__ import annotations

import json
import uuid
from typing import Any

from backend.app.core.paths import AppPaths
from backend.app.domain.models.common import SessionStatus
from backend.app.domain.models.project import ConsultantDossier
from backend.app.repositories.file_repository import FileRepository
from backend.app.repositories.sqlite_repository import SQLiteRepository
from backend.app.schemas.consultant import ConsultantSessionState, QuestionPayload


QUESTIONS: list[QuestionPayload] = [
    QuestionPayload(question_id="market_hook", prompt="这本书最抓读者的一句话卖点是什么？"),
    QuestionPayload(question_id="target_audience", prompt="你希望主打哪类核心读者？"),
    QuestionPayload(question_id="protagonist_design", prompt="主角的人设起点、性格和成长抓手是什么？"),
    QuestionPayload(question_id="golden_finger_design", prompt="金手指的核心规则、代价和升级空间是什么？"),
    QuestionPayload(question_id="core_conflict_engine", prompt="推动长线连载的核心冲突机制是什么？"),
    QuestionPayload(question_id="early_30_chapter_pacing", prompt="前30章准备如何安排爽点、升级和钩子？"),
]


class ConsultantService:
    def __init__(self, paths: AppPaths, file_repository: FileRepository, sqlite_repository: SQLiteRepository) -> None:
        self.paths = paths
        self.file_repository = file_repository
        self.sqlite_repository = sqlite_repository

    def start_session(
        self,
        project_id: str,
        brief: str,
        preferred_subgenres: list[str],
        constraints: list[str],
    ) -> ConsultantSessionState:
        project = self.sqlite_repository.get_project_record(project_id)
        if project is None:
            raise KeyError(project_id)

        now = self._now_iso()
        session_id = f"cs_{uuid.uuid4().hex[:12]}"
        self.sqlite_repository.create_consultant_session(
            {
                "session_id": session_id,
                "project_id": project_id,
                "status": SessionStatus.in_progress.value,
                "brief": brief,
                "preferred_subgenres_json": json.dumps(preferred_subgenres, ensure_ascii=False),
                "constraints_json": json.dumps(constraints, ensure_ascii=False),
                "current_question_index": 0,
                "total_questions": len(QUESTIONS),
                "answers_json": json.dumps({}, ensure_ascii=False),
                "dossier_path": None,
                "created_at": now,
                "updated_at": now,
            }
        )
        return self._build_state(self._require_session(session_id))

    def answer_session(self, session_id: str, question_id: str, answer: str) -> ConsultantSessionState:
        session = self._require_session(session_id)
        index = int(session["current_question_index"])
        if index >= len(QUESTIONS):
            raise ValueError("All questions have already been answered.")

        expected = QUESTIONS[index]
        if question_id != expected.question_id:
            raise ValueError("Question id does not match the current step.")

        answers = json.loads(session["answers_json"])
        answers[question_id] = answer
        new_index = index + 1
        self.sqlite_repository.update_consultant_session(
            session_id,
            {
                "answers_json": json.dumps(answers, ensure_ascii=False),
                "current_question_index": new_index,
                "updated_at": self._now_iso(),
            },
        )
        return self._build_state(self._require_session(session_id))

    def finalize_session(self, session_id: str) -> tuple[ConsultantDossier, str]:
        session = self._require_session(session_id)
        answers = json.loads(session["answers_json"])
        if len(answers) < len(QUESTIONS):
            raise ValueError("Cannot finalize before all questions are answered.")

        project = self.sqlite_repository.get_project_record(session["project_id"])
        if project is None:
            raise KeyError(session["project_id"])

        preferred_subgenres = json.loads(session["preferred_subgenres_json"])
        qa_transcript = [
            {
                "question_id": item.question_id,
                "prompt": item.prompt,
                "answer": answers.get(item.question_id, ""),
            }
            for item in QUESTIONS
        ]
        dossier = ConsultantDossier(
            dossier_id=f"dossier_{uuid.uuid4().hex[:12]}",
            project_id=project["project_id"],
            high_concept=f"{session['brief']}｜{answers['market_hook']}",
            subgenres=preferred_subgenres,
            target_audience=self._split_text_to_list(answers["target_audience"]),
            selling_points=[
                answers["market_hook"],
                answers["golden_finger_design"],
                answers["core_conflict_engine"],
            ],
            protagonist_seed={"summary": answers["protagonist_design"]},
            golden_finger={"summary": answers["golden_finger_design"]},
            core_conflicts=self._split_text_to_list(answers["core_conflict_engine"]),
            chapter_1_30_beats=[
                {"range": "1-10", "focus": f"起势与觉醒：{answers['early_30_chapter_pacing']}"},
                {"range": "11-20", "focus": f"升级与立威：{answers['early_30_chapter_pacing']}"},
                {"range": "21-30", "focus": f"破局与拉高期待：{answers['early_30_chapter_pacing']}"},
            ],
            qa_transcript=qa_transcript,
            version=1,
        )
        dossier_path = self.paths.consultant_dossier_path(project["slug"])
        self.file_repository.write_json(dossier_path, dossier.model_dump(mode="json"))
        self.sqlite_repository.update_consultant_session(
            session_id,
            {
                "status": SessionStatus.completed.value,
                "dossier_path": str(dossier_path),
                "updated_at": self._now_iso(),
            },
        )
        return dossier, str(dossier_path)

    def _build_state(self, session: dict[str, Any]) -> ConsultantSessionState:
        index = int(session["current_question_index"])
        current_question = QUESTIONS[index] if index < len(QUESTIONS) else None
        return ConsultantSessionState(
            session_id=session["session_id"],
            project_id=session["project_id"],
            status=session["status"],
            current_question=current_question,
            answered_count=index,
            total_questions=int(session["total_questions"]),
            ready_to_finalize=index >= len(QUESTIONS),
        )

    def _require_session(self, session_id: str) -> dict[str, Any]:
        session = self.sqlite_repository.get_consultant_session(session_id)
        if session is None:
            raise KeyError(session_id)
        return session

    def _split_text_to_list(self, value: str) -> list[str]:
        return [item.strip() for item in value.replace("，", ",").split(",") if item.strip()] or [value.strip()]

    def _now_iso(self) -> str:
        return __import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat()
