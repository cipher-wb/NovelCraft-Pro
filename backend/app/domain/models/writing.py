from __future__ import annotations

from datetime import datetime

from pydantic import Field

from backend.app.domain.models.common import DomainModel


class StoryAnchor(DomainModel):
    title: str = ""
    genre: str = ""
    subgenres: list[str] = Field(default_factory=list)
    logline: str = ""
    premise: str = ""
    selling_points: list[str] = Field(default_factory=list)
    core_conflicts: list[str] = Field(default_factory=list)
    story_promise: str = ""
    narrative_constraints: list[str] = Field(default_factory=list)
    world_hook: str = ""
    power_hook: str = ""


class VolumeAnchor(DomainModel):
    volume_id: str
    volume_no: int
    title: str = ""
    summary: str = ""
    goal: str = ""
    core_conflict: str = ""
    upgrade_target: str = ""


class ChapterAnchor(DomainModel):
    chapter_id: str
    chapter_no: int
    title: str = ""
    summary: str = ""
    purpose: str = ""
    main_conflict: str = ""
    hook: str = ""
    entry_state: list[str] = Field(default_factory=list)
    exit_state: list[str] = Field(default_factory=list)


class SceneAnchor(DomainModel):
    scene_id: str
    scene_no: int
    title: str = ""
    summary: str = ""
    scene_type: str = ""
    goal: str = ""
    obstacle: str = ""
    turning_point: str = ""
    outcome: str = ""
    location_id: str | None = None
    time_anchor: str = ""
    must_include: list[str] = Field(default_factory=list)
    forbidden: list[str] = Field(default_factory=list)
    target_words: int = 0
    emotional_beat: str = ""
    continuity_notes: str = ""


class CharacterBrief(DomainModel):
    character_id: str
    name: str
    role: str
    is_protagonist: bool = False
    archetype: str = ""
    realm_level: str = ""
    traits: list[str] = Field(default_factory=list)
    public_goal: str = ""
    private_goal: str = ""
    relationship_summaries: list[str] = Field(default_factory=list)


class FactionBrief(DomainModel):
    faction_id: str
    name: str
    goal: str = ""
    public_image: str = ""


class LocationBrief(DomainModel):
    location_id: str
    name: str
    type: str = ""
    description: str = ""
    tags: list[str] = Field(default_factory=list)


class PowerBrief(DomainModel):
    system_name: str = ""
    core_rules: list[str] = Field(default_factory=list)
    upgrade_rhythm_guideline: str = ""


class ContinuityBrief(DomainModel):
    previous_accepted_scene_id: str | None = None
    previous_accepted_scene_summary: str = ""


class ContextSourceVersions(DomainModel):
    story_bible_version: int = 0
    characters_version: int = 0
    world_version: int = 0
    power_system_version: int = 0
    volume_version: int = 0
    chapter_version: int = 0
    scene_version: int = 0


class AcceptedSceneMemoryItem(DomainModel):
    memory_id: str
    scene_id: str
    chapter_id: str
    volume_id: str
    draft_id: str
    chapter_no: int
    scene_no: int
    volume_no: int = 0
    chapter_title: str = ""
    scene_title: str
    scene_type: str = ""
    summary: str = ""
    summary_source: str = "draft_summary"
    scene_goal: str = ""
    scene_outcome: str = ""
    character_ids: list[str] = Field(default_factory=list)
    faction_ids: list[str] = Field(default_factory=list)
    location_id: str | None = None
    time_anchor: str = ""
    accepted_at: datetime
    source_scene_version: int = 0


class AcceptedSceneMemoryDocument(DomainModel):
    project_id: str
    version: int = 1
    updated_at: datetime
    items: list[AcceptedSceneMemoryItem] = Field(default_factory=list)


class ChapterSummaryMemoryItem(DomainModel):
    chapter_id: str
    volume_id: str
    chapter_no: int
    chapter_title: str = ""
    accepted_scene_ids: list[str] = Field(default_factory=list)
    accepted_scene_count: int = 0
    summary: str = ""
    summary_source: str = "accepted_scene_rollup"
    key_turns: list[str] = Field(default_factory=list)
    last_scene_id: str | None = None
    last_scene_no: int | None = None
    updated_from_draft_id: str | None = None
    updated_at: datetime


class ChapterSummariesMemoryDocument(DomainModel):
    project_id: str
    version: int = 1
    updated_at: datetime
    items: list[ChapterSummaryMemoryItem] = Field(default_factory=list)


class CharacterStateSummaryMemoryItem(DomainModel):
    character_id: str
    character_name: str = ""
    last_scene_id: str
    last_chapter_id: str
    last_volume_id: str
    last_chapter_no: int
    last_scene_no: int
    latest_location_id: str | None = None
    latest_time_anchor: str = ""
    latest_scene_summary: str = ""
    last_scene_goal: str = ""
    last_scene_outcome: str = ""
    related_character_ids: list[str] = Field(default_factory=list)
    source_draft_id: str
    updated_at: datetime


class CharacterStateSummariesMemoryDocument(DomainModel):
    project_id: str
    version: int = 1
    updated_at: datetime
    items: list[CharacterStateSummaryMemoryItem] = Field(default_factory=list)


class RetrievedSceneSummary(DomainModel):
    scene_id: str
    chapter_id: str
    scene_no: int
    scene_title: str = ""
    summary: str = ""
    scene_goal: str = ""
    scene_outcome: str = ""


class RetrievedPreviousChapterSummary(DomainModel):
    chapter_id: str
    chapter_no: int
    chapter_title: str = ""
    summary: str = ""
    key_turns: list[str] = Field(default_factory=list)


class RetrievedCharacterStateBrief(DomainModel):
    character_id: str
    character_name: str = ""
    last_scene_id: str
    last_chapter_no: int
    last_scene_no: int
    latest_location_id: str | None = None
    latest_scene_summary: str = ""
    last_scene_goal: str = ""
    last_scene_outcome: str = ""
    related_character_ids: list[str] = Field(default_factory=list)


class RetrievedMemoryContext(DomainModel):
    strategy: str = "deterministic_v1"
    warnings: list[str] = Field(default_factory=list)
    recent_scene_summaries: list[RetrievedSceneSummary] = Field(default_factory=list)
    previous_chapter_summary: RetrievedPreviousChapterSummary | None = None
    character_state_briefs: list[RetrievedCharacterStateBrief] = Field(default_factory=list)


class ContextBundle(DomainModel):
    context_bundle_id: str
    project_id: str
    volume_id: str
    chapter_id: str
    scene_id: str
    created_at: datetime
    source_versions: ContextSourceVersions
    story_anchor: StoryAnchor
    volume_anchor: VolumeAnchor
    chapter_anchor: ChapterAnchor
    scene_anchor: SceneAnchor
    character_briefs: list[CharacterBrief] = Field(default_factory=list)
    faction_briefs: list[FactionBrief] = Field(default_factory=list)
    location_brief: LocationBrief | None = None
    power_brief: PowerBrief | None = None
    continuity: ContinuityBrief = Field(default_factory=ContinuityBrief)
    retrieved_memory: RetrievedMemoryContext = Field(default_factory=RetrievedMemoryContext)


class SceneDraft(DomainModel):
    draft_id: str
    project_id: str
    volume_id: str
    chapter_id: str
    scene_id: str
    chapter_no: int
    scene_no: int
    draft_no: int
    operation: str
    candidate_mode: str
    status: str
    content_md: str
    summary: str = ""
    context_bundle_id: str | None = None
    context_bundle_path: str | None = None
    draft_path: str | None = None
    model_name: str = ""
    tokens_in: int = 0
    tokens_out: int = 0
    source_scene_version: int = 0
    source_chapter_version: int = 0
    source_volume_version: int = 0
    created_at: datetime
    updated_at: datetime
    accepted_at: datetime | None = None
    rejected_at: datetime | None = None
    supersedes_draft_id: str | None = None
    memory_stub_record_id: str | None = None


class SceneDraftManifestItem(DomainModel):
    draft_id: str
    draft_no: int
    status: str
    candidate_mode: str
    summary: str = ""
    draft_path: str
    context_bundle_path: str | None = None
    created_at: datetime
    accepted_at: datetime | None = None
    rejected_at: datetime | None = None


class SceneDraftManifest(DomainModel):
    project_id: str
    volume_id: str
    chapter_id: str
    scene_id: str
    version: int = 1
    updated_at: datetime
    latest_draft_id: str | None = None
    accepted_draft_id: str | None = None
    last_draft_no: int = 0
    items: list[SceneDraftManifestItem] = Field(default_factory=list)


class MemoryIngestResult(DomainModel):
    accepted_scene_item: AcceptedSceneMemoryItem
    chapter_summary_item: ChapterSummaryMemoryItem | None = None
    character_state_count: int = 0


class CharacterStateSnapshot(DomainModel):
    snapshot_id: str
    project_id: str
    character_id: str
    chapter_id: str
    scene_id: str | None = None
    realm_level: str = ""
    health_status: str = ""
    location: str = ""
    inventory: list[str] = Field(default_factory=list)
    alliances: list[str] = Field(default_factory=list)
    hostilities: list[str] = Field(default_factory=list)
    goals: list[str] = Field(default_factory=list)
    emotion: str = ""
    knowledge: list[str] = Field(default_factory=list)
    created_at: datetime


class TimelineEvent(DomainModel):
    event_id: str
    project_id: str
    chapter_id: str
    scene_id: str | None = None
    time_order: int
    event_time: str = ""
    title: str
    description: str = ""
    participants: list[str] = Field(default_factory=list)
    location: str = ""
    event_type: str = ""
    causes: list[str] = Field(default_factory=list)
    effects: list[str] = Field(default_factory=list)
    source_version_id: str | None = None


class DraftVersion(DomainModel):
    version_id: str
    project_id: str
    scope: str
    scope_id: str
    base_version_id: str | None = None
    source_draft_id: str | None = None
    content_md: str
    change_note: str = ""
    created_by: str
    created_at: datetime
    checksum: str = ""
    snapshot_path: str
    is_active: bool = True
