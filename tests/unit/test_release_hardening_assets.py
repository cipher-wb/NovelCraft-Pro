from __future__ import annotations

import json
from pathlib import Path


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def test_phase11_docs_and_release_assets_are_present() -> None:
    repo_root = _repo_root()

    readme = (repo_root / "README.md").read_text(encoding="utf-8")
    demo = (repo_root / "docs" / "demo-workflow.md").read_text(encoding="utf-8")
    checklist = (repo_root / "docs" / "release-checklist.md").read_text(encoding="utf-8")
    release_template = (repo_root / "docs" / "releases" / "TEMPLATE.md").read_text(encoding="utf-8")

    assert "当前稳定阶段 = Phase 11（Release Hardening / Pre-Ship Cleanup Minimal Chain）" in readme
    assert "Quick Start" in readme
    assert "examples/sample-project-package/" in readme
    assert "POST /api/projects/import-package" in readme
    assert "POST /api/projects/{project_id}/archive-snapshot" in readme
    assert "POST /api/projects/{project_id}/backup" in readme
    assert "GET /api/projects/{project_id}/snapshots" in readme

    assert "examples/sample-project-package/" in demo
    assert "proj_phase11_demo" in demo
    assert "overall_status\": \"clean\"" in demo

    assert "## Must Pass Before Release" in checklist
    assert "## Known Limitations Accepted For This Release" in checklist

    for heading in [
        "## Summary",
        "## Included Capabilities",
        "## Verified Commands",
        "## Known Limitations",
        "## Commit Hash",
    ]:
        assert heading in release_template


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
