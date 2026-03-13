from __future__ import annotations

from pathlib import Path

from backend.app.core.config import Settings


class AppPaths:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    @property
    def data_root(self) -> Path:
        return self.settings.data_root

    @property
    def projects_root(self) -> Path:
        return self.settings.projects_root

    @property
    def app_db_path(self) -> Path:
        return self.data_root / "app.db"

    def ensure_runtime_dirs(self) -> None:
        self.data_root.mkdir(parents=True, exist_ok=True)
        self.projects_root.mkdir(parents=True, exist_ok=True)

    def project_root(self, slug: str) -> Path:
        return self.projects_root / slug

    def relative_to_project(self, slug: str, path: Path) -> str:
        return path.relative_to(self.project_root(slug)).as_posix()

    def project_manifest_path(self, slug: str) -> Path:
        return self.project_root(slug) / "project.json"

    def consultant_dir(self, slug: str) -> Path:
        return self.project_root(slug) / "consultant"

    def consultant_sessions_dir(self, slug: str) -> Path:
        return self.consultant_dir(slug) / "sessions"

    def consultant_dossier_path(self, slug: str) -> Path:
        return self.consultant_dir(slug) / "dossier.json"

    def bible_dir(self, slug: str) -> Path:
        return self.project_root(slug) / "bible"

    def story_bible_path(self, slug: str) -> Path:
        return self.bible_dir(slug) / "story_bible.json"

    def characters_path(self, slug: str) -> Path:
        return self.bible_dir(slug) / "characters.json"

    def world_path(self, slug: str) -> Path:
        return self.bible_dir(slug) / "world.json"

    def power_system_path(self, slug: str) -> Path:
        return self.bible_dir(slug) / "power_system.json"

    def voice_profile_path(self, slug: str) -> Path:
        return self.bible_dir(slug) / "voice_profile.json"

    def plans_dir(self, slug: str) -> Path:
        return self.project_root(slug) / "plans"

    def master_outline_path(self, slug: str) -> Path:
        return self.plans_dir(slug) / "master_outline.json"

    def volumes_dir(self, slug: str) -> Path:
        return self.plans_dir(slug) / "volumes"

    def chapters_dir(self, slug: str) -> Path:
        return self.plans_dir(slug) / "chapters"

    def scenes_dir(self, slug: str) -> Path:
        return self.plans_dir(slug) / "scenes"

    def volume_plan_path(self, slug: str, volume_no: int) -> Path:
        return self.volumes_dir(slug) / f"volume-{volume_no:03d}.json"

    def chapter_plan_path(self, slug: str, chapter_no: int) -> Path:
        return self.chapters_dir(slug) / f"chapter-{chapter_no:04d}.json"

    def scene_plan_path(self, slug: str, chapter_no: int, scene_no: int) -> Path:
        return self.scenes_dir(slug) / f"chapter-{chapter_no:04d}-scene-{scene_no:03d}.json"

    def drafts_dir(self, slug: str) -> Path:
        return self.project_root(slug) / "drafts"

    def scene_drafts_root(self, slug: str) -> Path:
        return self.drafts_dir(slug) / "scenes"

    def chapter_drafts_root(self, slug: str) -> Path:
        return self.drafts_dir(slug) / "chapters"

    def volume_drafts_root(self, slug: str) -> Path:
        return self.drafts_dir(slug) / "volumes"

    def book_drafts_root(self, slug: str) -> Path:
        return self.drafts_dir(slug) / "book"

    def scene_drafts_dir(self, slug: str, scene_id: str) -> Path:
        return self.scene_drafts_root(slug) / scene_id

    def chapter_drafts_dir(self, slug: str, chapter_id: str) -> Path:
        return self.chapter_drafts_root(slug) / chapter_id

    def volume_drafts_dir(self, slug: str, volume_id: str) -> Path:
        return self.volume_drafts_root(slug) / volume_id

    def book_drafts_dir(self, slug: str) -> Path:
        return self.book_drafts_root(slug)

    def scene_draft_manifest_path(self, slug: str, scene_id: str) -> Path:
        return self.scene_drafts_dir(slug, scene_id) / "manifest.json"

    def chapter_assembled_path(self, slug: str, chapter_id: str) -> Path:
        return self.chapter_drafts_dir(slug, chapter_id) / "assembled.json"

    def volume_assembled_path(self, slug: str, volume_id: str) -> Path:
        return self.volume_drafts_dir(slug, volume_id) / "assembled.json"

    def book_assembled_path(self, slug: str) -> Path:
        return self.book_drafts_dir(slug) / "assembled.json"

    def scene_draft_path(self, slug: str, scene_id: str, draft_no: int) -> Path:
        return self.scene_drafts_dir(slug, scene_id) / f"draft-{draft_no:03d}.json"

    def scene_context_bundle_path(self, slug: str, scene_id: str, draft_no: int) -> Path:
        return self.scene_drafts_dir(slug, scene_id) / f"context-bundle-{draft_no:03d}.json"

    def scene_checks_dir(self, slug: str, scene_id: str) -> Path:
        return self.scene_drafts_dir(slug, scene_id) / "checks"

    def chapter_checks_dir(self, slug: str, chapter_id: str) -> Path:
        return self.chapter_drafts_dir(slug, chapter_id) / "checks"

    def volume_checks_dir(self, slug: str, volume_id: str) -> Path:
        return self.volume_drafts_dir(slug, volume_id) / "checks"

    def book_checks_dir(self, slug: str) -> Path:
        return self.book_drafts_dir(slug) / "checks"

    def book_continuity_checks_dir(self, slug: str) -> Path:
        return self.book_drafts_dir(slug) / "continuity_checks"

    def scene_draft_check_report_path(self, slug: str, scene_id: str, draft_id: str) -> Path:
        return self.scene_checks_dir(slug, scene_id) / f"{draft_id}.json"

    def chapter_check_latest_path(self, slug: str, chapter_id: str) -> Path:
        return self.chapter_checks_dir(slug, chapter_id) / "latest.json"

    def volume_check_latest_path(self, slug: str, volume_id: str) -> Path:
        return self.volume_checks_dir(slug, volume_id) / "latest.json"

    def book_check_latest_path(self, slug: str) -> Path:
        return self.book_checks_dir(slug) / "latest.json"

    def book_continuity_check_latest_path(self, slug: str) -> Path:
        return self.book_continuity_checks_dir(slug) / "latest.json"

    def memory_dir(self, slug: str) -> Path:
        return self.project_root(slug) / "memory"

    def accepted_scenes_memory_path(self, slug: str) -> Path:
        return self.memory_dir(slug) / "accepted_scenes.json"

    def chapter_summaries_memory_path(self, slug: str) -> Path:
        return self.memory_dir(slug) / "chapter_summaries.json"

    def volume_summaries_memory_path(self, slug: str) -> Path:
        return self.memory_dir(slug) / "volume_summaries.json"

    def book_summary_memory_path(self, slug: str) -> Path:
        return self.memory_dir(slug) / "book_summary.json"

    def character_state_summaries_memory_path(self, slug: str) -> Path:
        return self.memory_dir(slug) / "character_state_summaries.json"

    def meta_dir(self, slug: str) -> Path:
        return self.project_root(slug) / ".meta"

    def vectorstore_dir(self, slug: str) -> Path:
        return self.meta_dir(slug) / "vectorstore"
