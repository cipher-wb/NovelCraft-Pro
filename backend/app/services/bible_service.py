from __future__ import annotations

import uuid
from typing import Any

from backend.app.core.paths import AppPaths
from backend.app.domain.models.common import utc_now
from backend.app.domain.models.planning import ChapterPlan, MasterOutlineDocument, ScenePlan
from backend.app.domain.models.project import (
    CharacterCard,
    CharacterDocument,
    CharacterRelationship,
    ConsultantDossier,
    PowerSystemDocument,
    StoryBible,
    WorldDocument,
)
from backend.app.repositories.file_repository import FileRepository
from backend.app.repositories.sqlite_repository import SQLiteRepository
from backend.app.schemas.bible import BibleAggregateResponse
from backend.app.services.exceptions import ConflictError


class BibleService:
    def __init__(self, paths: AppPaths, file_repository: FileRepository, sqlite_repository: SQLiteRepository) -> None:
        self.paths = paths
        self.file_repository = file_repository
        self.sqlite_repository = sqlite_repository

    def initialize_from_consultant(self, project_id: str, overwrite: bool = False) -> BibleAggregateResponse:
        project = self._require_project(project_id)
        slug = project["slug"]
        dossier_path = self.paths.consultant_dossier_path(slug)
        if not self.file_repository.exists(dossier_path):
            raise ValueError("Consultant dossier does not exist.")

        existing = self.get_bible_aggregate(project_id)
        if not overwrite and self._is_bible_initialized(existing):
            raise ConflictError("Bible documents already initialized.")

        dossier = ConsultantDossier.model_validate(self.file_repository.read_json(dossier_path))
        protagonist_id = "char_mc"
        now = utc_now()
        story_bible = StoryBible(
            bible_id=f"bible_{project_id}",
            project_id=project_id,
            source_dossier_id=dossier.dossier_id,
            title=project["title"],
            genre=project["genre"],
            subgenres=dossier.subgenres,
            target_audience=dossier.target_audience,
            logline=dossier.high_concept,
            premise=dossier.high_concept,
            themes=[],
            selling_points=dossier.selling_points,
            core_conflicts=dossier.core_conflicts,
            story_promise=dossier.selling_points[0] if dossier.selling_points else dossier.high_concept,
            narrative_constraints=dossier.subgenres,
            protagonist_ids=[protagonist_id],
            featured_faction_ids=[],
            featured_location_ids=[],
            world_hook=dossier.core_conflicts[0] if dossier.core_conflicts else "",
            power_hook=dossier.golden_finger.get("summary", ""),
            status="draft",
            version=1,
            updated_at=now,
        )
        protagonist = CharacterCard(
            character_id=protagonist_id,
            project_id=project_id,
            name="主角",
            role="protagonist",
            is_protagonist=True,
            archetype="升级流主角",
            public_goal=dossier.protagonist_seed.get("summary", ""),
            private_goal=dossier.core_conflicts[0] if dossier.core_conflicts else "",
            traits=["成长"],
            notes=[dossier.protagonist_seed.get("summary", "")],
            version=1,
        )
        characters = CharacterDocument(
            project_id=project_id,
            status="draft",
            version=1,
            updated_at=now,
            items=[protagonist],
        )
        world = WorldDocument(
            project_id=project_id,
            status="draft",
            version=1,
            updated_at=now,
            setting_scope=dossier.subgenres[0] if dossier.subgenres else project["genre"],
            tone="爽文快节奏",
        )
        power_system = PowerSystemDocument(
            project_id=project_id,
            status="draft",
            version=1,
            updated_at=now,
            system_name=dossier.golden_finger.get("summary", "未命名体系"),
            source_type="mixed",
            core_rules=[dossier.golden_finger.get("summary", "")],
            upgrade_rhythm_guideline=dossier.chapter_1_30_beats[0]["focus"] if dossier.chapter_1_30_beats else "",
        )
        self._write_story_bible(slug, story_bible)
        self._write_characters(slug, characters)
        self._write_world(slug, world)
        self._write_power_system(slug, power_system)
        return self.get_bible_aggregate(project_id)

    def get_bible_aggregate(self, project_id: str) -> BibleAggregateResponse:
        project = self._require_project(project_id)
        slug = project["slug"]
        story_bible = self._read_story_bible(slug)
        characters = self._read_characters(slug)
        world = self._read_world(slug)
        power_system = self._read_power_system(slug)
        statuses = [story_bible.status, characters.status, world.status, power_system.status]
        aggregate_status = "ready"
        if "stale" in statuses:
            aggregate_status = "stale"
        elif "draft" in statuses:
            aggregate_status = "draft"
        return BibleAggregateResponse(
            story_bible=story_bible,
            characters=characters,
            world=world,
            power_system=power_system,
            aggregate_status=aggregate_status,
        )

    def update_story_bible(self, project_id: str, payload: dict[str, Any], partial: bool = True) -> StoryBible:
        project = self._require_project(project_id)
        slug = project["slug"]
        existing = self._read_story_bible(slug)
        updated = self._merge_model(existing, payload, StoryBible)
        updated.status = "draft"
        updated.version = existing.version + 1
        updated.updated_at = utc_now()
        self._write_story_bible(slug, updated)
        self._mark_all_plans_stale(slug)
        return updated

    def update_world(self, project_id: str, payload: dict[str, Any], partial: bool = True) -> WorldDocument:
        project = self._require_project(project_id)
        slug = project["slug"]
        existing = self._read_world(slug)
        updated = self._merge_model(existing, payload, WorldDocument)
        updated.status = "draft"
        updated.version = existing.version + 1
        updated.updated_at = utc_now()
        self._write_world(slug, updated)
        self._mark_all_plans_stale(slug)
        return updated

    def update_power_system(self, project_id: str, payload: dict[str, Any], partial: bool = True) -> PowerSystemDocument:
        project = self._require_project(project_id)
        slug = project["slug"]
        existing = self._read_power_system(slug)
        updated = self._merge_model(existing, payload, PowerSystemDocument)
        updated.status = "draft"
        updated.version = existing.version + 1
        updated.updated_at = utc_now()
        self._write_power_system(slug, updated)
        self._mark_all_plans_stale(slug)
        return updated

    def create_character(self, project_id: str, payload: dict[str, Any]) -> CharacterCard:
        project = self._require_project(project_id)
        slug = project["slug"]
        characters = self._read_characters(slug)
        item = CharacterCard(
            character_id=f"char_{uuid.uuid4().hex[:8]}",
            project_id=project_id,
            name=payload["name"],
            role=payload["role"],
            is_protagonist=payload.get("is_protagonist", False),
            aliases=payload.get("aliases", []),
            archetype=payload.get("archetype", ""),
            core_desire=payload.get("core_desire", ""),
            core_fear=payload.get("core_fear", ""),
            secret=payload.get("secret", ""),
            realm_level=payload.get("realm_level", ""),
            traits=payload.get("traits", []),
            public_goal=payload.get("public_goal", ""),
            private_goal=payload.get("private_goal", ""),
            faction_id=payload.get("faction_id"),
            first_appearance_hint=payload.get("first_appearance_hint", ""),
            relationships=[CharacterRelationship.model_validate(item) for item in payload.get("relationships", [])],
            notes=payload.get("notes", []),
            status="draft",
            version=1,
        )
        characters.items.append(item)
        characters.status = "draft"
        characters.version += 1
        characters.updated_at = utc_now()
        self._write_characters(slug, characters)
        self._mark_all_plans_stale(slug)
        return item

    def update_character(self, project_id: str, character_id: str, payload: dict[str, Any]) -> CharacterCard:
        project = self._require_project(project_id)
        slug = project["slug"]
        characters = self._read_characters(slug)
        for index, item in enumerate(characters.items):
            if item.character_id == character_id:
                updated_payload = item.model_dump(mode="python")
                updated_payload.update(payload)
                if "relationships" in updated_payload:
                    updated_payload["relationships"] = [CharacterRelationship.model_validate(value) for value in updated_payload["relationships"]]
                updated_payload["version"] = item.version + 1
                updated_payload["status"] = "draft"
                updated = CharacterCard.model_validate(updated_payload)
                characters.items[index] = updated
                characters.status = "draft"
                characters.version += 1
                characters.updated_at = utc_now()
                self._write_characters(slug, characters)
                self._mark_all_plans_stale(slug)
                return updated
        raise KeyError(character_id)

    def delete_character(self, project_id: str, character_id: str) -> None:
        project = self._require_project(project_id)
        slug = project["slug"]
        characters = self._read_characters(slug)
        if self._character_is_referenced(slug, character_id):
            raise ConflictError("Character is referenced by structured story or plan data.")
        new_items = [item for item in characters.items if item.character_id != character_id]
        if len(new_items) == len(characters.items):
            raise KeyError(character_id)
        characters.items = new_items
        characters.status = "draft"
        characters.version += 1
        characters.updated_at = utc_now()
        self._write_characters(slug, characters)
        self._mark_all_plans_stale(slug)

    def get_character(self, project_id: str, character_id: str) -> CharacterCard:
        project = self._require_project(project_id)
        slug = project["slug"]
        characters = self._read_characters(slug)
        for item in characters.items:
            if item.character_id == character_id:
                return item
        raise KeyError(character_id)

    def confirm_story_bible(self, project_id: str) -> StoryBible:
        project = self._require_project(project_id)
        slug = project["slug"]
        story_bible = self._read_story_bible(slug)
        if story_bible.status == "stale":
            raise ConflictError("Stale story bible cannot be confirmed directly.")
        if story_bible.status == "ready":
            return story_bible
        characters = self._read_characters(slug)
        world = self._read_world(slug)
        character_ids = {item.character_id for item in characters.items}
        faction_ids = {item.faction_id for item in world.factions}
        location_ids = {item.location_id for item in world.locations}
        if not set(story_bible.protagonist_ids).issubset(character_ids):
            raise ValueError("Protagonist references are not resolvable.")
        if not set(story_bible.featured_faction_ids).issubset(faction_ids):
            raise ValueError("Featured faction references are not resolvable.")
        if not set(story_bible.featured_location_ids).issubset(location_ids):
            raise ValueError("Featured location references are not resolvable.")
        story_bible.status = "ready"
        story_bible.version += 1
        story_bible.updated_at = utc_now()
        self._write_story_bible(slug, story_bible)
        return story_bible

    def confirm_world(self, project_id: str) -> WorldDocument:
        project = self._require_project(project_id)
        slug = project["slug"]
        world = self._read_world(slug)
        if world.status == "stale":
            raise ConflictError("Stale world document cannot be confirmed directly.")
        if world.status == "ready":
            return world
        rule_ids = [item.rule_id for item in world.world_rules]
        faction_ids = [item.faction_id for item in world.factions]
        location_ids = [item.location_id for item in world.locations]
        if len(rule_ids) != len(set(rule_ids)):
            raise ValueError("Duplicate world rule ids.")
        if len(faction_ids) != len(set(faction_ids)):
            raise ValueError("Duplicate faction ids.")
        if len(location_ids) != len(set(location_ids)):
            raise ValueError("Duplicate location ids.")
        world.status = "ready"
        world.version += 1
        world.updated_at = utc_now()
        self._write_world(slug, world)
        return world

    def confirm_power_system(self, project_id: str) -> PowerSystemDocument:
        project = self._require_project(project_id)
        slug = project["slug"]
        power_system = self._read_power_system(slug)
        if power_system.status == "stale":
            raise ConflictError("Stale power system document cannot be confirmed directly.")
        if power_system.status == "ready":
            return power_system
        orders = [item.order for item in power_system.realm_ladder]
        if len(orders) != len(set(orders)):
            raise ValueError("Duplicate realm order values.")
        power_system.status = "ready"
        power_system.version += 1
        power_system.updated_at = utc_now()
        self._write_power_system(slug, power_system)
        return power_system

    def confirm_characters(self, project_id: str) -> CharacterDocument:
        project = self._require_project(project_id)
        slug = project["slug"]
        characters = self._read_characters(slug)
        if characters.status == "stale":
            raise ConflictError("Stale character document cannot be confirmed directly.")
        if characters.status == "ready":
            return characters
        world = self._read_world(slug)
        faction_ids = {item.faction_id for item in world.factions}
        character_ids = [item.character_id for item in characters.items]
        if len(character_ids) != len(set(character_ids)):
            raise ValueError("Duplicate character ids.")
        for item in characters.items:
            if item.faction_id is not None and item.faction_id not in faction_ids:
                raise ValueError("Character faction reference is not resolvable.")
        characters.status = "ready"
        characters.version += 1
        characters.updated_at = utc_now()
        self._write_characters(slug, characters)
        return characters

    def _merge_model(self, model: Any, payload: dict[str, Any], model_cls: Any) -> Any:
        data = model.model_dump(mode="python")
        data.update(payload)
        return model_cls.model_validate(data)

    def _is_bible_initialized(self, aggregate: BibleAggregateResponse) -> bool:
        return bool(
            aggregate.story_bible.source_dossier_id
            or aggregate.characters.items
            or aggregate.world.world_rules
            or aggregate.world.factions
            or aggregate.world.locations
            or aggregate.power_system.system_name
            or aggregate.power_system.core_rules
        )

    def _character_is_referenced(self, slug: str, character_id: str) -> bool:
        if character_id in self._read_story_bible(slug).protagonist_ids:
            return True
        for path in sorted(self.paths.chapters_dir(slug).glob("*.json")):
            chapter = ChapterPlan.model_validate(self.file_repository.read_json(path))
            if character_id in chapter.character_ids:
                return True
        for path in sorted(self.paths.scenes_dir(slug).glob("*.json")):
            scene = ScenePlan.model_validate(self.file_repository.read_json(path))
            if character_id in scene.character_ids:
                return True
        return False

    def _mark_all_plans_stale(self, slug: str) -> None:
        outline_path = self.paths.master_outline_path(slug)
        if self.file_repository.exists(outline_path):
            outline = MasterOutlineDocument.model_validate(self.file_repository.read_json(outline_path))
            outline.outline_status = "stale"
            outline.version += 1
            outline.updated_at = utc_now()
            self.file_repository.write_json(outline_path, outline.model_dump(mode="json"))
        for directory in (self.paths.volumes_dir(slug), self.paths.chapters_dir(slug), self.paths.scenes_dir(slug)):
            if not directory.exists():
                continue
            for file_path in directory.glob("*.json"):
                payload = self.file_repository.read_json(file_path)
                payload["status"] = "stale"
                payload["stale_reason"] = "upstream_bible_changed"
                self.file_repository.write_json(file_path, payload)

    def _require_project(self, project_id: str) -> dict[str, Any]:
        project = self.sqlite_repository.get_project_record(project_id)
        if project is None:
            raise KeyError(project_id)
        return project

    def _read_story_bible(self, slug: str) -> StoryBible:
        return StoryBible.model_validate(self.file_repository.read_json(self.paths.story_bible_path(slug)))

    def _read_characters(self, slug: str) -> CharacterDocument:
        return CharacterDocument.model_validate(self.file_repository.read_json(self.paths.characters_path(slug)))

    def _read_world(self, slug: str) -> WorldDocument:
        return WorldDocument.model_validate(self.file_repository.read_json(self.paths.world_path(slug)))

    def _read_power_system(self, slug: str) -> PowerSystemDocument:
        return PowerSystemDocument.model_validate(self.file_repository.read_json(self.paths.power_system_path(slug)))

    def _write_story_bible(self, slug: str, story_bible: StoryBible) -> None:
        self.file_repository.write_json(self.paths.story_bible_path(slug), story_bible.model_dump(mode="json"))

    def _write_characters(self, slug: str, characters: CharacterDocument) -> None:
        self.file_repository.write_json(self.paths.characters_path(slug), characters.model_dump(mode="json"))

    def _write_world(self, slug: str, world: WorldDocument) -> None:
        self.file_repository.write_json(self.paths.world_path(slug), world.model_dump(mode="json"))

    def _write_power_system(self, slug: str, power_system: PowerSystemDocument) -> None:
        self.file_repository.write_json(self.paths.power_system_path(slug), power_system.model_dump(mode="json"))
