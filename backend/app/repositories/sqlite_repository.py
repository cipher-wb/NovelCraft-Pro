from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

from backend.app.infra.db import connect_sqlite, initialize_workspace_db


class SQLiteRepository:
    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path

    def initialize(self) -> None:
        initialize_workspace_db(self.db_path)

    def _connect(self) -> sqlite3.Connection:
        return connect_sqlite(self.db_path)

    def create_project_record(self, record: dict[str, Any]) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO projects (
                    project_id, slug, title, genre, status, target_chapters, target_words,
                    root_path, manifest_path, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record["project_id"],
                    record["slug"],
                    record["title"],
                    record["genre"],
                    record["status"],
                    record["target_chapters"],
                    record["target_words"],
                    record["root_path"],
                    record["manifest_path"],
                    record["created_at"],
                    record["updated_at"],
                ),
            )
            connection.commit()

    def list_project_records(self) -> list[dict[str, Any]]:
        with self._connect() as connection:
            rows = connection.execute("SELECT * FROM projects ORDER BY created_at ASC").fetchall()
        return [dict(row) for row in rows]

    def get_project_record(self, project_id: str) -> dict[str, Any] | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM projects WHERE project_id = ?",
                (project_id,),
            ).fetchone()
        return dict(row) if row is not None else None

    def get_project_record_by_slug(self, slug: str) -> dict[str, Any] | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM projects WHERE slug = ?",
                (slug,),
            ).fetchone()
        return dict(row) if row is not None else None

    def create_consultant_session(self, record: dict[str, Any]) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO consultant_sessions (
                    session_id, project_id, status, brief, preferred_subgenres_json,
                    constraints_json, current_question_index, total_questions,
                    answers_json, dossier_path, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record["session_id"],
                    record["project_id"],
                    record["status"],
                    record["brief"],
                    record["preferred_subgenres_json"],
                    record["constraints_json"],
                    record["current_question_index"],
                    record["total_questions"],
                    record["answers_json"],
                    record.get("dossier_path"),
                    record["created_at"],
                    record["updated_at"],
                ),
            )
            connection.commit()

    def update_consultant_session(self, session_id: str, updates: dict[str, Any]) -> None:
        if not updates:
            return
        assignments = ", ".join(f"{key} = ?" for key in updates)
        values = list(updates.values()) + [session_id]
        with self._connect() as connection:
            connection.execute(
                f"UPDATE consultant_sessions SET {assignments} WHERE session_id = ?",
                values,
            )
            connection.commit()

    def get_consultant_session(self, session_id: str) -> dict[str, Any] | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM consultant_sessions WHERE session_id = ?",
                (session_id,),
            ).fetchone()
        return dict(row) if row is not None else None
