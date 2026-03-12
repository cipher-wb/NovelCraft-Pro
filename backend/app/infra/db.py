from __future__ import annotations

import sqlite3
from pathlib import Path


PROJECTS_SCHEMA = """
CREATE TABLE IF NOT EXISTS projects (
    project_id TEXT PRIMARY KEY,
    slug TEXT UNIQUE NOT NULL,
    title TEXT NOT NULL,
    genre TEXT NOT NULL,
    status TEXT NOT NULL,
    target_chapters INTEGER NOT NULL,
    target_words INTEGER NOT NULL,
    root_path TEXT NOT NULL,
    manifest_path TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
)
"""

CONSULTANT_SESSIONS_SCHEMA = """
CREATE TABLE IF NOT EXISTS consultant_sessions (
    session_id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL,
    status TEXT NOT NULL,
    brief TEXT NOT NULL,
    preferred_subgenres_json TEXT NOT NULL,
    constraints_json TEXT NOT NULL,
    current_question_index INTEGER NOT NULL,
    total_questions INTEGER NOT NULL,
    answers_json TEXT NOT NULL,
    dossier_path TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
)
"""


def connect_sqlite(db_path: Path) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(db_path)
    connection.row_factory = sqlite3.Row
    return connection


def initialize_workspace_db(db_path: Path) -> None:
    with connect_sqlite(db_path) as connection:
        connection.execute(PROJECTS_SCHEMA)
        connection.execute(CONSULTANT_SESSIONS_SCHEMA)
        connection.commit()
