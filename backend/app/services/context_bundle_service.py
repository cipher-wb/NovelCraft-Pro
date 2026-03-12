from __future__ import annotations

import uuid

from backend.app.core.paths import AppPaths
from backend.app.domain.models.common import utc_now
from backend.app.domain.models.project import CharacterCard, Faction, Location
from backend.app.domain.models.writing import (
    ChapterAnchor,
    CharacterBrief,
    ContextBundle,
    ContextSourceVersions,
    ContinuityBrief,
    FactionBrief,
    LocationBrief,
    PowerBrief,
    SceneAnchor,
    StoryAnchor,
    VolumeAnchor,
)
from backend.app.repositories.file_repository import FileRepository
from backend.app.services.bible_service import BibleService
from backend.app.services.planner_service import PlannerService
from backend.app.services.retrieval_service import RetrievalService


class ContextBundleService:
    def __init__(
        self,
        paths: AppPaths,
        file_repository: FileRepository,
        bible_service: BibleService,
        planner_service: PlannerService,
        retrieval_service: RetrievalService,
    ) -> None:
        self.paths = paths
        self.file_repository = file_repository
        self.bible_service = bible_service
        self.planner_service = planner_service
        self.retrieval_service = retrieval_service

    def build(self, project_id: str, scene_id: str) -> ContextBundle:
        project = self.bible_service._require_project(project_id)
        aggregate = self.bible_service.get_bible_aggregate(project_id)
        scene = self.planner_service.get_scene(project_id, scene_id)
        chapter = self.planner_service.get_chapter(project_id, scene.chapter_id)
        volume = self.planner_service.get_volume(project_id, scene.volume_id)

        scene_character_ids = set(scene.character_ids)
        faction_ids = set(chapter.faction_ids)
        location = next((item for item in aggregate.world.locations if item.location_id == scene.location_id), None)
        retrieved_memory = self.retrieval_service.retrieve_for_scene(project_id, scene_id)
        previous_summary = retrieved_memory.recent_scene_summaries[0] if retrieved_memory.recent_scene_summaries else None

        return ContextBundle(
            context_bundle_id=f"ctx_{uuid.uuid4().hex[:12]}",
            project_id=project_id,
            volume_id=volume.volume_id,
            chapter_id=chapter.chapter_id,
            scene_id=scene.scene_id,
            created_at=utc_now(),
            source_versions=ContextSourceVersions(
                story_bible_version=aggregate.story_bible.version,
                characters_version=aggregate.characters.version,
                world_version=aggregate.world.version,
                power_system_version=aggregate.power_system.version,
                volume_version=volume.version,
                chapter_version=chapter.version,
                scene_version=scene.version,
            ),
            story_anchor=StoryAnchor(
                title=aggregate.story_bible.title,
                genre=aggregate.story_bible.genre,
                subgenres=aggregate.story_bible.subgenres,
                logline=aggregate.story_bible.logline,
                premise=aggregate.story_bible.premise,
                selling_points=aggregate.story_bible.selling_points[:2],
                core_conflicts=aggregate.story_bible.core_conflicts[:2],
                story_promise=aggregate.story_bible.story_promise,
                narrative_constraints=aggregate.story_bible.narrative_constraints[:4],
                world_hook=aggregate.story_bible.world_hook,
                power_hook=aggregate.story_bible.power_hook,
            ),
            volume_anchor=VolumeAnchor(
                volume_id=volume.volume_id,
                volume_no=volume.volume_no,
                title=volume.title,
                summary=volume.summary,
                goal=volume.goal,
                core_conflict=volume.core_conflict,
                upgrade_target=volume.upgrade_target,
            ),
            chapter_anchor=ChapterAnchor(
                chapter_id=chapter.chapter_id,
                chapter_no=chapter.chapter_no,
                title=chapter.title,
                summary=chapter.summary,
                purpose=chapter.purpose,
                main_conflict=chapter.main_conflict,
                hook=chapter.hook,
                entry_state=chapter.entry_state,
                exit_state=chapter.exit_state,
            ),
            scene_anchor=SceneAnchor(
                scene_id=scene.scene_id,
                scene_no=scene.scene_no,
                title=scene.title,
                summary=scene.summary,
                scene_type=scene.scene_type,
                goal=scene.goal,
                obstacle=scene.obstacle,
                turning_point=scene.turning_point,
                outcome=scene.outcome,
                location_id=scene.location_id,
                time_anchor=scene.time_anchor,
                must_include=scene.must_include,
                forbidden=scene.forbidden,
                target_words=scene.target_words,
                emotional_beat=scene.emotional_beat,
                continuity_notes=scene.continuity_notes,
            ),
            character_briefs=[self._to_character_brief(item, scene_character_ids) for item in aggregate.characters.items if item.character_id in scene_character_ids],
            faction_briefs=[self._to_faction_brief(item) for item in aggregate.world.factions if item.faction_id in faction_ids],
            location_brief=self._to_location_brief(location),
            power_brief=PowerBrief(
                system_name=aggregate.power_system.system_name,
                core_rules=aggregate.power_system.core_rules[:2],
                upgrade_rhythm_guideline=aggregate.power_system.upgrade_rhythm_guideline,
            ),
            continuity=ContinuityBrief(
                previous_accepted_scene_id=previous_summary.scene_id if previous_summary else None,
                previous_accepted_scene_summary=previous_summary.summary if previous_summary else "",
            ),
            retrieved_memory=retrieved_memory,
        )

    def _to_character_brief(self, item: CharacterCard, in_scene_ids: set[str]) -> CharacterBrief:
        return CharacterBrief(
            character_id=item.character_id,
            name=item.name,
            role=item.role,
            is_protagonist=item.is_protagonist,
            archetype=item.archetype,
            realm_level=item.realm_level,
            traits=item.traits[:3],
            public_goal=item.public_goal,
            private_goal=item.private_goal,
            relationship_summaries=[
                relation.summary or relation.relation_type
                for relation in item.relationships
                if relation.target_character_id in in_scene_ids
            ],
        )

    def _to_faction_brief(self, item: Faction) -> FactionBrief:
        return FactionBrief(
            faction_id=item.faction_id,
            name=item.name,
            goal=item.goal,
            public_image=item.public_image,
        )

    def _to_location_brief(self, item: Location | None) -> LocationBrief | None:
        if item is None:
            return None
        return LocationBrief(
            location_id=item.location_id,
            name=item.name,
            type=item.type,
            description=item.description,
            tags=item.tags,
        )
