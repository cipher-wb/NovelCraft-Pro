from __future__ import annotations

from pathlib import Path



def test_sqlite_repository_initializes_schema_and_roundtrips_records(workspace_tmp_dir: Path) -> None:
    from backend.app.repositories.sqlite_repository import SQLiteRepository

    db_path = workspace_tmp_dir / "app.db"
    repo = SQLiteRepository(db_path)
    repo.initialize()

    repo.create_project_record(
        {
            "project_id": "proj_001",
            "slug": "my-book",
            "title": "我的新书",
            "genre": "修仙爽文",
            "status": "bootstrapped",
            "target_chapters": 300,
            "target_words": 2_000_000,
            "root_path": "projects/my-book",
            "manifest_path": "projects/my-book/project.json",
            "created_at": "2026-03-12T00:00:00Z",
            "updated_at": "2026-03-12T00:00:00Z"
        }
    )

    repo.create_consultant_session(
        {
            "session_id": "cs_001",
            "project_id": "proj_001",
            "status": "in_progress",
            "brief": "都市修仙打脸升级流",
            "preferred_subgenres_json": '["都市异能","升级流"]',
            "constraints_json": '["作者主导"]',
            "current_question_index": 0,
            "total_questions": 6,
            "answers_json": "{}",
            "dossier_path": None,
            "created_at": "2026-03-12T00:00:00Z",
            "updated_at": "2026-03-12T00:00:00Z"
        }
    )

    project = repo.get_project_record("proj_001")
    session = repo.get_consultant_session("cs_001")
    project_items = repo.list_project_records()

    assert project is not None
    assert project["slug"] == "my-book"
    assert session is not None
    assert session["project_id"] == "proj_001"
    assert len(project_items) == 1
