from __future__ import annotations

import math
from pathlib import Path
from typing import Any

from backend.app.core.paths import AppPaths
from backend.app.domain.models.common import utc_now
from backend.app.domain.models.planning import ChapterPlan, MasterOutlineDocument, OutlineVolumeRef, ScenePlan, VolumePlan
from backend.app.repositories.file_repository import FileRepository
from backend.app.repositories.sqlite_repository import SQLiteRepository
from backend.app.services.bible_service import BibleService
from backend.app.services.exceptions import ConflictError


class PlannerService:
    def __init__(
        self,
        paths: AppPaths,
        file_repository: FileRepository,
        sqlite_repository: SQLiteRepository,
        bible_service: BibleService,
    ) -> None:
        self.paths = paths
        self.file_repository = file_repository
        self.sqlite_repository = sqlite_repository
        self.bible_service = bible_service

    def get_master_outline(self, project_id: str) -> MasterOutlineDocument:
        project = self._require_project(project_id)
        return self._read_outline(project["slug"])

    def generate_volumes(
        self,
        project_id: str,
        overwrite: bool = False,
        volume_count_hint: int | None = None,
        chapters_per_volume_hint: int | None = None,
    ) -> MasterOutlineDocument:
        project = self._require_project(project_id)
        slug = project["slug"]
        aggregate = self.bible_service.get_bible_aggregate(project_id)
        if aggregate.aggregate_status != "ready":
            raise ValueError("Bible aggregate must be ready before generating volumes.")
        outline = self._read_outline(slug)
        if not overwrite and outline.volumes:
            raise ConflictError("Master outline already exists.")

        chapters_per_volume = chapters_per_volume_hint or 30
        volume_count = volume_count_hint or max(1, math.ceil(project["target_chapters"] / chapters_per_volume))
        remaining = project["target_chapters"]
        volume_refs: list[OutlineVolumeRef] = []
        for index in range(1, volume_count + 1):
            planned_chapters = min(chapters_per_volume, remaining) if index < volume_count else max(1, remaining)
            remaining = max(0, remaining - planned_chapters)
            self._ensure_unique_volume_no(slug, index)
            volume_id = f"volume_{index:03d}"
            file_path = self.paths.volume_plan_path(slug, index)
            if file_path.exists() and not overwrite:
                raise ConflictError("Volume plan target already exists.")
            title_suffix = aggregate.story_bible.selling_points[0] if aggregate.story_bible.selling_points else aggregate.story_bible.story_promise or "主线推进"
            volume = VolumePlan(
                volume_id=volume_id,
                project_id=project_id,
                volume_no=index,
                title=f"第{index}卷 {title_suffix}",
                summary=f"围绕 {title_suffix} 的卷级脚手架",
                goal=aggregate.story_bible.story_promise,
                core_conflict=aggregate.story_bible.core_conflicts[0] if aggregate.story_bible.core_conflicts else "",
                opening_hook=aggregate.story_bible.logline,
                closing_hook=f"卷{index}收束并抛出下卷问题",
                upgrade_target=aggregate.power_system.system_name,
                entry_state=[aggregate.story_bible.premise] if aggregate.story_bible.premise else [],
                exit_state=[aggregate.story_bible.story_promise] if aggregate.story_bible.story_promise else [],
                major_beats=aggregate.story_bible.selling_points[:3],
                planned_chapters=planned_chapters,
                chapter_ids=[],
                source_bible_version=aggregate.story_bible.version,
                status="draft",
                version=1,
                stale_reason=None,
            )
            self._write_volume(slug, volume)
            volume_refs.append(self._outline_ref_from_volume(volume, file_path))
        outline.outline_status = "draft"
        outline.version += 1
        outline.updated_at = utc_now()
        outline.source_bible_version = aggregate.story_bible.version
        outline.total_volumes = len(volume_refs)
        outline.active_volume_id = volume_refs[0].volume_id if volume_refs else None
        outline.volumes = volume_refs
        self._write_outline(slug, outline)
        return outline

    def list_volumes(self, project_id: str) -> list[VolumePlan]:
        project = self._require_project(project_id)
        slug = project["slug"]
        items = [VolumePlan.model_validate(self.file_repository.read_json(path)) for path in sorted(self.paths.volumes_dir(slug).glob("*.json"))]
        return sorted(items, key=lambda item: item.volume_no)

    def get_volume(self, project_id: str, volume_id: str) -> VolumePlan:
        volume, _ = self._find_volume(project_id, volume_id)
        return volume

    def update_volume(self, project_id: str, volume_id: str, payload: dict[str, Any]) -> VolumePlan:
        project = self._require_project(project_id)
        slug = project["slug"]
        volume, path = self._find_volume(project_id, volume_id)
        old_volume_no = volume.volume_no
        updated_data = volume.model_dump(mode="python")
        updated_data.update(payload)
        if "volume_no" in payload:
            self._ensure_unique_volume_no(slug, int(payload["volume_no"]), exclude_volume_id=volume_id)
        updated_data["status"] = "draft"
        updated_data["version"] = volume.version + 1
        updated = VolumePlan.model_validate(updated_data)
        new_path = self.paths.volume_plan_path(slug, updated.volume_no)
        self._write_volume(slug, updated)
        if new_path != path and path.exists():
            path.unlink()
        if updated.volume_no != old_volume_no:
            self._propagate_volume_no_to_children(slug, volume_id, updated.volume_no)
        self._sync_outline_volume_ref(slug, updated, mark_stale=True)
        self._mark_descendants_stale_for_volume(slug, volume_id)
        return updated

    def confirm_volume(self, project_id: str, volume_id: str) -> VolumePlan:
        volume, path = self._find_volume(project_id, volume_id)
        if volume.status == "stale":
            raise ConflictError("Stale volume cannot be confirmed directly.")
        if volume.status == "ready":
            return volume
        self._validate_global_volume_numbers(project_id)
        for chapter_id in volume.chapter_ids:
            self._find_chapter(project_id, chapter_id)
        volume.status = "ready"
        volume.version += 1
        self.file_repository.write_json(path, volume.model_dump(mode="json"))
        return volume

    def generate_chapters(self, project_id: str, volume_id: str, overwrite: bool = False) -> list[ChapterPlan]:
        project = self._require_project(project_id)
        slug = project["slug"]
        volume, volume_path = self._find_volume(project_id, volume_id)
        if volume.status != "ready":
            raise ValueError("Volume must be ready before generating chapters.")
        if volume.chapter_ids and not overwrite:
            raise ConflictError("Chapter plans already exist for this volume.")

        max_existing = self._max_chapter_no(slug)
        chapter_ids: list[str] = []
        items: list[ChapterPlan] = []
        for index in range(1, max(1, volume.planned_chapters) + 1):
            chapter_no = max_existing + index
            self._ensure_unique_chapter_no(slug, chapter_no)
            chapter_id = f"chapter_{chapter_no:04d}"
            path = self.paths.chapter_plan_path(slug, chapter_no)
            if path.exists() and not overwrite:
                raise ConflictError("Chapter plan target already exists.")
            chapter = ChapterPlan(
                chapter_id=chapter_id,
                project_id=project_id,
                volume_id=volume_id,
                volume_no=volume.volume_no,
                chapter_no=chapter_no,
                title=f"第{chapter_no}章 {volume.title}推进{index}",
                summary=f"围绕 {volume.goal} 的章节脚手架",
                purpose=f"推进卷目标的第{index}步",
                main_conflict=volume.core_conflict,
                hook=volume.closing_hook if index == volume.planned_chapters else f"章节{index}结尾钩子",
                entry_state=volume.entry_state,
                exit_state=volume.exit_state,
                character_ids=[],
                faction_ids=[],
                foreshadow_ids=[],
                payoff_ids=[],
                target_words=3000,
                scene_ids=[],
                source_volume_version=volume.version,
                status="draft",
                version=1,
                stale_reason=None,
            )
            self._write_chapter(slug, chapter)
            chapter_ids.append(chapter_id)
            items.append(chapter)
        volume.chapter_ids = chapter_ids
        volume.version += 1
        self.file_repository.write_json(volume_path, volume.model_dump(mode="json"))
        self._sync_outline_volume_ref(slug, volume, mark_stale=False)
        return items

    def list_chapters(self, project_id: str, volume_id: str) -> list[ChapterPlan]:
        self._require_project(project_id)
        items = [item for item in self._all_chapters(project_id) if item.volume_id == volume_id]
        return sorted(items, key=lambda item: item.chapter_no)

    def get_chapter(self, project_id: str, chapter_id: str) -> ChapterPlan:
        chapter, _ = self._find_chapter(project_id, chapter_id)
        return chapter

    def update_chapter(self, project_id: str, chapter_id: str, payload: dict[str, Any]) -> ChapterPlan:
        project = self._require_project(project_id)
        slug = project["slug"]
        chapter, path = self._find_chapter(project_id, chapter_id)
        old_chapter_no = chapter.chapter_no
        updated_data = chapter.model_dump(mode="python")
        updated_data.update(payload)
        if "chapter_no" in payload:
            self._ensure_unique_chapter_no(slug, int(payload["chapter_no"]), exclude_chapter_id=chapter_id)
        updated_data["status"] = "draft"
        updated_data["version"] = chapter.version + 1
        updated = ChapterPlan.model_validate(updated_data)
        new_path = self.paths.chapter_plan_path(slug, updated.chapter_no)
        self._write_chapter(slug, updated)
        if new_path != path and path.exists():
            path.unlink()
        if updated.chapter_no != old_chapter_no:
            self._renumber_chapter_scenes(slug, chapter.chapter_id, updated.chapter_no)
        self._mark_outline_stale(slug)
        self._mark_volume_stale(slug, chapter.volume_id)
        self._mark_descendants_stale_for_chapter(slug, chapter.chapter_id)
        return updated

    def confirm_chapter(self, project_id: str, chapter_id: str) -> ChapterPlan:
        chapter, path = self._find_chapter(project_id, chapter_id)
        if chapter.status == "stale":
            raise ConflictError("Stale chapter cannot be confirmed directly.")
        if chapter.status == "ready":
            return chapter
        aggregate = self.bible_service.get_bible_aggregate(project_id)
        character_ids = {item.character_id for item in aggregate.characters.items}
        faction_ids = {item.faction_id for item in aggregate.world.factions}
        if len(chapter.character_ids) != len(set(chapter.character_ids)):
            raise ValueError("Duplicate character ids in chapter.")
        if len(chapter.faction_ids) != len(set(chapter.faction_ids)):
            raise ValueError("Duplicate faction ids in chapter.")
        if not set(chapter.character_ids).issubset(character_ids):
            raise ValueError("Chapter character references are not resolvable.")
        if not set(chapter.faction_ids).issubset(faction_ids):
            raise ValueError("Chapter faction references are not resolvable.")
        self._validate_global_chapter_numbers(project_id)
        chapter.status = "ready"
        chapter.version += 1
        self.file_repository.write_json(path, chapter.model_dump(mode="json"))
        return chapter

    def generate_scenes(
        self,
        project_id: str,
        chapter_id: str,
        overwrite: bool = False,
        scene_count_hint: int | None = None,
    ) -> list[ScenePlan]:
        project = self._require_project(project_id)
        slug = project["slug"]
        chapter, chapter_path = self._find_chapter(project_id, chapter_id)
        if chapter.status != "ready":
            raise ValueError("Chapter must be ready before generating scenes.")
        if chapter.scene_ids and not overwrite:
            raise ConflictError("Scene plans already exist for this chapter.")

        scene_count = scene_count_hint or 3
        scene_ids: list[str] = []
        items: list[ScenePlan] = []
        scene_types = ["setup", "pressure", "turn", "payoff", "transition"]
        for index in range(1, scene_count + 1):
            self._ensure_unique_scene_no(slug, chapter.chapter_id, index)
            scene_id = f"scene_{chapter.chapter_no:04d}_{index:03d}"
            path = self.paths.scene_plan_path(slug, chapter.chapter_no, index)
            if path.exists() and not overwrite:
                raise ConflictError("Scene plan target already exists.")
            scene = ScenePlan(
                scene_id=scene_id,
                project_id=project_id,
                volume_id=chapter.volume_id,
                chapter_id=chapter_id,
                chapter_no=chapter.chapter_no,
                scene_no=index,
                title=f"场景{index}",
                summary=f"章节 {chapter.chapter_no} 的场景脚手架 {index}",
                scene_type=scene_types[min(index - 1, len(scene_types) - 1)],
                goal=chapter.purpose,
                obstacle=chapter.main_conflict,
                turning_point=chapter.hook,
                outcome=f"场景{index}完成阶段推进",
                location_id=None,
                time_anchor="",
                character_ids=chapter.character_ids,
                must_include=[],
                forbidden=[],
                target_words=max(800, chapter.target_words // scene_count),
                emotional_beat="",
                continuity_notes="",
                source_chapter_version=chapter.version,
                status="draft",
                version=1,
                stale_reason=None,
            )
            self._write_scene(slug, scene)
            scene_ids.append(scene_id)
            items.append(scene)
        chapter.scene_ids = scene_ids
        chapter.version += 1
        self.file_repository.write_json(chapter_path, chapter.model_dump(mode="json"))
        return items

    def list_scenes(self, project_id: str, chapter_id: str) -> list[ScenePlan]:
        self._require_project(project_id)
        items = [item for item in self._all_scenes(project_id) if item.chapter_id == chapter_id]
        return sorted(items, key=lambda item: item.scene_no)

    def get_scene(self, project_id: str, scene_id: str) -> ScenePlan:
        scene, _ = self._find_scene(project_id, scene_id)
        return scene

    def update_scene(self, project_id: str, scene_id: str, payload: dict[str, Any]) -> ScenePlan:
        project = self._require_project(project_id)
        slug = project["slug"]
        scene, path = self._find_scene(project_id, scene_id)
        old_scene_no = scene.scene_no
        updated_data = scene.model_dump(mode="python")
        updated_data.update(payload)
        if "scene_no" in payload:
            self._ensure_unique_scene_no(slug, scene.chapter_id, int(payload["scene_no"]), exclude_scene_id=scene_id)
        updated_data["status"] = "draft"
        updated_data["version"] = scene.version + 1
        updated = ScenePlan.model_validate(updated_data)
        new_path = self.paths.scene_plan_path(slug, updated.chapter_no, updated.scene_no)
        self._write_scene(slug, updated)
        if new_path != path and path.exists():
            path.unlink()
        if updated.scene_no != old_scene_no:
            self._validate_scene_numbers(project_id, scene.chapter_id)
        self._mark_outline_stale(slug)
        self._mark_volume_stale(slug, scene.volume_id)
        self._mark_chapter_stale(slug, scene.chapter_id)
        return updated

    def confirm_scene(self, project_id: str, scene_id: str) -> ScenePlan:
        scene, path = self._find_scene(project_id, scene_id)
        if scene.status == "stale":
            raise ConflictError("Stale scene cannot be confirmed directly.")
        if scene.status == "ready":
            return scene
        aggregate = self.bible_service.get_bible_aggregate(project_id)
        character_ids = {item.character_id for item in aggregate.characters.items}
        location_ids = {item.location_id for item in aggregate.world.locations}
        if not set(scene.character_ids).issubset(character_ids):
            raise ValueError("Scene character references are not resolvable.")
        if scene.location_id is not None and scene.location_id not in location_ids:
            raise ValueError("Scene location reference is not resolvable.")
        self._validate_scene_numbers(project_id, scene.chapter_id)
        scene.status = "ready"
        scene.version += 1
        self.file_repository.write_json(path, scene.model_dump(mode="json"))
        return scene

    def confirm_master_outline(self, project_id: str) -> MasterOutlineDocument:
        project = self._require_project(project_id)
        slug = project["slug"]
        outline = self._read_outline(slug)
        if outline.outline_status == "stale":
            raise ConflictError("Stale master outline cannot be confirmed directly.")
        if outline.outline_status == "ready":
            return outline
        for ref in outline.volumes:
            path = self.paths.project_root(slug) / ref.file_path
            if not path.exists():
                raise ValueError("Referenced volume file does not exist.")
            volume = VolumePlan.model_validate(self.file_repository.read_json(path))
            if volume.volume_id != ref.volume_id or volume.volume_no != ref.volume_no:
                raise ValueError("Volume reference does not match target file.")
        outline.outline_status = "ready"
        outline.version += 1
        self._write_outline(slug, outline)
        return outline

    def _outline_ref_from_volume(self, volume: VolumePlan, file_path: Path) -> OutlineVolumeRef:
        return OutlineVolumeRef(
            volume_id=volume.volume_id,
            volume_no=volume.volume_no,
            title=volume.title,
            summary=volume.summary,
            goal=volume.goal,
            planned_chapters=volume.planned_chapters,
            status=volume.status,
            file_path=f"plans/volumes/{file_path.name}",
        )

    def _sync_outline_volume_ref(self, slug: str, volume: VolumePlan, *, mark_stale: bool) -> None:
        outline = self._read_outline(slug)
        changed = False
        for index, ref in enumerate(outline.volumes):
            if ref.volume_id == volume.volume_id:
                outline.volumes[index] = self._outline_ref_from_volume(volume, self.paths.volume_plan_path(slug, volume.volume_no))
                changed = True
                break
        if changed or mark_stale:
            if mark_stale:
                outline.outline_status = "stale"
                outline.version += 1
            self._write_outline(slug, outline)

    def _propagate_volume_no_to_children(self, slug: str, volume_id: str, volume_no: int) -> None:
        for path in sorted(self.paths.chapters_dir(slug).glob("*.json")):
            chapter = ChapterPlan.model_validate(self.file_repository.read_json(path))
            if chapter.volume_id != volume_id:
                continue
            chapter.volume_no = volume_no
            chapter.version += 1
            self.file_repository.write_json(path, chapter.model_dump(mode="json"))

    def _renumber_chapter_scenes(self, slug: str, chapter_id: str, chapter_no: int) -> None:
        scene_records: list[tuple[ScenePlan, Path]] = []
        for path in sorted(self.paths.scenes_dir(slug).glob("*.json")):
            scene = ScenePlan.model_validate(self.file_repository.read_json(path))
            if scene.chapter_id == chapter_id:
                scene_records.append((scene, path))
        for scene, path in scene_records:
            scene.chapter_no = chapter_no
            scene.version += 1
            new_path = self.paths.scene_plan_path(slug, chapter_no, scene.scene_no)
            self.file_repository.write_json(new_path, scene.model_dump(mode="json"))
            if new_path != path and path.exists():
                path.unlink()

    def _mark_outline_stale(self, slug: str) -> None:
        outline = self._read_outline(slug)
        outline.outline_status = "stale"
        outline.version += 1
        self._write_outline(slug, outline)

    def _mark_volume_stale(self, slug: str, volume_id: str) -> None:
        try:
            volume, path = self._find_volume_by_slug(slug, volume_id)
        except KeyError:
            return
        volume.status = "stale"
        volume.version += 1
        volume.stale_reason = "upstream_changed"
        self.file_repository.write_json(path, volume.model_dump(mode="json"))
        self._sync_outline_volume_ref(slug, volume, mark_stale=False)

    def _mark_chapter_stale(self, slug: str, chapter_id: str) -> None:
        try:
            chapter, path = self._find_chapter_by_slug(slug, chapter_id)
        except KeyError:
            return
        chapter.status = "stale"
        chapter.version += 1
        chapter.stale_reason = "upstream_changed"
        self.file_repository.write_json(path, chapter.model_dump(mode="json"))

    def _mark_descendants_stale_for_volume(self, slug: str, volume_id: str) -> None:
        for path in sorted(self.paths.chapters_dir(slug).glob("*.json")):
            payload = self.file_repository.read_json(path)
            if payload["volume_id"] == volume_id:
                payload["status"] = "stale"
                payload["stale_reason"] = "volume_changed"
                self.file_repository.write_json(path, payload)
        for path in sorted(self.paths.scenes_dir(slug).glob("*.json")):
            payload = self.file_repository.read_json(path)
            if payload["volume_id"] == volume_id:
                payload["status"] = "stale"
                payload["stale_reason"] = "volume_changed"
                self.file_repository.write_json(path, payload)

    def _mark_descendants_stale_for_chapter(self, slug: str, chapter_id: str) -> None:
        for path in sorted(self.paths.scenes_dir(slug).glob("*.json")):
            payload = self.file_repository.read_json(path)
            if payload["chapter_id"] == chapter_id:
                payload["status"] = "stale"
                payload["stale_reason"] = "chapter_changed"
                self.file_repository.write_json(path, payload)

    def _max_chapter_no(self, slug: str) -> int:
        max_value = 0
        for path in self.paths.chapters_dir(slug).glob("*.json"):
            payload = self.file_repository.read_json(path)
            max_value = max(max_value, int(payload["chapter_no"]))
        return max_value

    def _ensure_unique_volume_no(self, slug: str, volume_no: int, exclude_volume_id: str | None = None) -> None:
        for path in sorted(self.paths.volumes_dir(slug).glob("*.json")):
            volume = VolumePlan.model_validate(self.file_repository.read_json(path))
            if volume.volume_id == exclude_volume_id:
                continue
            if volume.volume_no == volume_no:
                raise ValueError("Volume numbers must be unique within the project.")

    def _ensure_unique_chapter_no(self, slug: str, chapter_no: int, exclude_chapter_id: str | None = None) -> None:
        for path in sorted(self.paths.chapters_dir(slug).glob("*.json")):
            chapter = ChapterPlan.model_validate(self.file_repository.read_json(path))
            if chapter.chapter_id == exclude_chapter_id:
                continue
            if chapter.chapter_no == chapter_no:
                raise ValueError("Chapter numbers must be unique within the project.")

    def _ensure_unique_scene_no(self, slug: str, chapter_id: str, scene_no: int, exclude_scene_id: str | None = None) -> None:
        for path in sorted(self.paths.scenes_dir(slug).glob("*.json")):
            scene = ScenePlan.model_validate(self.file_repository.read_json(path))
            if scene.scene_id == exclude_scene_id:
                continue
            if scene.chapter_id == chapter_id and scene.scene_no == scene_no:
                raise ValueError("Scene numbers must be unique within the chapter.")

    def _validate_global_volume_numbers(self, project_id: str) -> None:
        values = [volume.volume_no for volume in self.list_volumes(project_id)]
        if len(values) != len(set(values)):
            raise ValueError("Volume numbers must be unique within the project.")

    def _validate_global_chapter_numbers(self, project_id: str) -> None:
        values = [chapter.chapter_no for chapter in self._all_chapters(project_id)]
        if len(values) != len(set(values)):
            raise ValueError("Chapter numbers must be unique within the project.")

    def _validate_scene_numbers(self, project_id: str, chapter_id: str) -> None:
        values = [scene.scene_no for scene in self._all_scenes(project_id) if scene.chapter_id == chapter_id]
        if len(values) != len(set(values)):
            raise ValueError("Scene numbers must be unique within the chapter.")

    def _all_chapters(self, project_id: str) -> list[ChapterPlan]:
        project = self._require_project(project_id)
        return [ChapterPlan.model_validate(self.file_repository.read_json(path)) for path in sorted(self.paths.chapters_dir(project["slug"]).glob("*.json"))]

    def _all_scenes(self, project_id: str) -> list[ScenePlan]:
        project = self._require_project(project_id)
        return [ScenePlan.model_validate(self.file_repository.read_json(path)) for path in sorted(self.paths.scenes_dir(project["slug"]).glob("*.json"))]

    def _require_project(self, project_id: str) -> dict[str, Any]:
        project = self.sqlite_repository.get_project_record(project_id)
        if project is None:
            raise KeyError(project_id)
        return project

    def _read_outline(self, slug: str) -> MasterOutlineDocument:
        return MasterOutlineDocument.model_validate(self.file_repository.read_json(self.paths.master_outline_path(slug)))

    def _write_outline(self, slug: str, outline: MasterOutlineDocument) -> None:
        outline.updated_at = utc_now()
        self.file_repository.write_json(self.paths.master_outline_path(slug), outline.model_dump(mode="json"))

    def _write_volume(self, slug: str, volume: VolumePlan) -> None:
        self.file_repository.write_json(self.paths.volume_plan_path(slug, volume.volume_no), volume.model_dump(mode="json"))

    def _write_chapter(self, slug: str, chapter: ChapterPlan) -> None:
        self.file_repository.write_json(self.paths.chapter_plan_path(slug, chapter.chapter_no), chapter.model_dump(mode="json"))

    def _write_scene(self, slug: str, scene: ScenePlan) -> None:
        self.file_repository.write_json(self.paths.scene_plan_path(slug, scene.chapter_no, scene.scene_no), scene.model_dump(mode="json"))

    def _find_volume(self, project_id: str, volume_id: str) -> tuple[VolumePlan, Path]:
        project = self._require_project(project_id)
        return self._find_volume_by_slug(project["slug"], volume_id)

    def _find_volume_by_slug(self, slug: str, volume_id: str) -> tuple[VolumePlan, Path]:
        for path in sorted(self.paths.volumes_dir(slug).glob("*.json")):
            volume = VolumePlan.model_validate(self.file_repository.read_json(path))
            if volume.volume_id == volume_id:
                return volume, path
        raise KeyError(volume_id)

    def _find_chapter(self, project_id: str, chapter_id: str) -> tuple[ChapterPlan, Path]:
        project = self._require_project(project_id)
        return self._find_chapter_by_slug(project["slug"], chapter_id)

    def _find_chapter_by_slug(self, slug: str, chapter_id: str) -> tuple[ChapterPlan, Path]:
        for path in sorted(self.paths.chapters_dir(slug).glob("*.json")):
            chapter = ChapterPlan.model_validate(self.file_repository.read_json(path))
            if chapter.chapter_id == chapter_id:
                return chapter, path
        raise KeyError(chapter_id)

    def _find_scene(self, project_id: str, scene_id: str) -> tuple[ScenePlan, Path]:
        project = self._require_project(project_id)
        slug = project["slug"]
        for path in sorted(self.paths.scenes_dir(slug).glob("*.json")):
            scene = ScenePlan.model_validate(self.file_repository.read_json(path))
            if scene.scene_id == scene_id:
                return scene, path
        raise KeyError(scene_id)


