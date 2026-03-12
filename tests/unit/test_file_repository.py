from __future__ import annotations

from pathlib import Path



def test_file_repository_reads_and_writes_json_and_text(workspace_tmp_dir: Path) -> None:
    from backend.app.repositories.file_repository import FileRepository

    repo = FileRepository()
    json_path = workspace_tmp_dir / "nested" / "sample.json"
    text_path = workspace_tmp_dir / "nested" / "sample.txt"

    payload = {"title": "测试", "count": 3}

    repo.write_json(json_path, payload)
    repo.write_text(text_path, "hello")

    assert repo.exists(json_path) is True
    assert repo.exists(text_path) is True
    assert repo.read_json(json_path) == payload
    assert repo.read_text(text_path) == "hello"
