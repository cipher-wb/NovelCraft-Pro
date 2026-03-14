from __future__ import annotations

import json
from pathlib import Path


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def test_phase11_docs_and_release_assets_are_present() -> None:
    repo_root = _repo_root()

    readme = (repo_root / "README.md").read_text(encoding="utf-8")
    manual = (repo_root / "使用说明书.md").read_text(encoding="utf-8")
    demo = (repo_root / "docs" / "demo-workflow.md").read_text(encoding="utf-8")
    checklist = (repo_root / "docs" / "release-checklist.md").read_text(encoding="utf-8")
    release_template = (repo_root / "docs" / "releases" / "TEMPLATE.md").read_text(encoding="utf-8")
    release_notes = (repo_root / "docs" / "releases" / "v0.11.0.md").read_text(encoding="utf-8")

    assert "当前稳定阶段 = Phase 11（Release Hardening / Pre-Ship Cleanup Minimal Chain）" in readme
    assert "快速开始" in readme
    assert "Quick Start" not in readme
    assert "examples/sample-project-package/" in readme
    assert "POST /api/projects/import-package" in readme
    assert "POST /api/projects/{project_id}/archive-snapshot" in readme
    assert "POST /api/projects/{project_id}/backup" in readme
    assert "GET /api/projects/{project_id}/snapshots" in readme
    assert "项目体检" in readme
    assert "导出项目包" in readme

    assert "使用说明书" in manual
    assert "最短成功路径" in manual
    assert "项目体检" in manual
    assert "快速开始" not in manual

    assert "examples/sample-project-package/" in demo
    assert "proj_phase11_demo" in demo
    assert "overall_status\": \"clean\"" in demo
    assert "# 演示流程" in demo
    assert "打开工作台" in demo
    assert "Project Health" not in demo

    assert "# 发布检查清单" in checklist
    assert "## 发布前必须通过" in checklist
    assert "## 本次发布接受的已知限制" in checklist

    for heading in [
        "## 摘要",
        "## 包含能力",
        "## 已验证命令",
        "## 已知限制",
        "## 提交哈希",
    ]:
        assert heading in release_template

    assert "# 发布说明：v0.11.0" in release_notes
    assert "## 摘要" in release_notes
    assert "## 演示流程" in release_notes
    assert "## 已知限制" in release_notes


def test_studio_pages_are_localized_to_chinese() -> None:
    studio_root = _repo_root() / "backend" / "app" / "static" / "studio"
    index = (studio_root / "index.html").read_text(encoding="utf-8")
    scene = (studio_root / "scene.html").read_text(encoding="utf-8")
    chapter = (studio_root / "chapter.html").read_text(encoding="utf-8")
    volume = (studio_root / "volume.html").read_text(encoding="utf-8")
    book = (studio_root / "book.html").read_text(encoding="utf-8")
    style = (studio_root / "style.html").read_text(encoding="utf-8")

    assert "项目体检" in index
    assert "加载体检" in index
    assert "导出项目包" in index
    assert "导入项目包" in index
    assert "创建归档快照" in index
    assert "创建备份" in index
    assert "加载快照列表" in index
    assert "Project Health" not in index
    assert "Load Health" not in index
    assert "Import Package" not in index

    assert "场景草稿页面" in index
    assert "章节组装页面" in index
    assert "卷组装页面" in index
    assert "整书组装页面" in index

    assert "章节组装工作台" in chapter
    assert "组装章节" in chapter
    assert "重新检查" in chapter
    assert "导出章节" in chapter
    assert "Chapter Assembly Studio" not in chapter
    assert "Assemble Chapter" not in chapter

    assert "卷组装工作台" in volume
    assert "组装卷" in volume
    assert "导出卷" in volume
    assert "Volume Assembly Studio" not in volume

    assert "整书组装工作台" in book
    assert "组装整书" in book
    assert "重跑连续性检查" in book
    assert "导出整书" in book
    assert "Book Assembly Studio" not in book
    assert "Continuity Checks" not in book

    assert "场景草稿工作台" in scene
    assert "生成草稿" in scene
    assert "接受草稿" in scene
    assert "拒绝草稿" in scene
    assert "导出场景" in scene
    assert "Export Scene" not in scene

    assert "风格配置" in style
    assert "加载配置" in style
    assert "保存配置" in style
    assert "Style Profile" not in style
    assert "Enabled" not in style


def test_sample_project_package_has_importable_phase11_shape() -> None:
    package_root = _repo_root() / "examples" / "sample-project-package"
    manifest = json.loads((package_root / "manifest.json").read_text(encoding="utf-8"))
    inventory = json.loads((package_root / "inventory.json").read_text(encoding="utf-8"))

    assert manifest["scope"] == "project"
    assert manifest["package_version"] == "project_package_v1"
    assert manifest["format"] == "json_package"
    assert manifest["included_files"] == [
        "manifest.json",
        "inventory.json",
        "canonical/",
        "derived/",
        "memory/",
        "checks/",
    ]

    relative_paths = [item["relative_path"] for item in inventory["items"]]
    assert relative_paths == sorted(relative_paths)
    assert "canonical/project.json" in relative_paths
    assert "canonical/bible/story_bible.json" in relative_paths
    assert "canonical/plans/master_outline.json" in relative_paths
    assert "derived/drafts/book/assembled.json" in relative_paths
    assert "memory/book_summary.json" in relative_paths
    assert "checks/book/continuity_checks/latest.json" in relative_paths
    assert not any(path.startswith("exports/") for path in relative_paths)
    assert not any(path.startswith("archives/") for path in relative_paths)
    assert not any(path.startswith("backups/") for path in relative_paths)
