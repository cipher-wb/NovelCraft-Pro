from __future__ import annotations

from datetime import datetime

from pydantic import Field

from backend.app.domain.models.common import DomainModel
from backend.app.domain.models.style import StyleConstraintBundle


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
    hook: str = ""
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


class RetrievedVolumeSummary(DomainModel):
    volume_id: str
    volume_no: int
    title: str = ""
    summary: str = ""
    hook: str = ""
    planned_chapter_count: int = 0
    finalized_chapter_count: int = 0
    selection_reason: str = ""


class RetrievedBookSummary(DomainModel):
    summary: str = ""
    hook: str = ""
    planned_volume_count: int = 0
    finalized_volume_count: int = 0
    finalized_volume_ids: list[str] = Field(default_factory=list)


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
    previous_volume_summary: RetrievedVolumeSummary | None = None
    character_state_briefs: list[RetrievedCharacterStateBrief] = Field(default_factory=list)
    book_summary: RetrievedBookSummary | None = None


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
    style_constraints: StyleConstraintBundle = Field(default_factory=StyleConstraintBundle)
    retrieved_memory: RetrievedMemoryContext = Field(default_factory=RetrievedMemoryContext)


class RepairMetadata(DomainModel):
    source_draft_id: str
    source_check_run_id: str
    source_check_report_path: str
    selected_issue_ids: list[str] = Field(default_factory=list)
    selected_blocker_issue_ids: list[str] = Field(default_factory=list)
    selected_warning_issue_ids: list[str] = Field(default_factory=list)
    repair_strategy_version: str = "targeted_repair_v1"
    repair_summary: str = ""


class ChapterAssembledSourceVersions(DomainModel):
    volume_version: int = 0
    chapter_version: int = 0
    scene_versions: dict[str, int] = Field(default_factory=dict)
    accepted_draft_ids: dict[str, str] = Field(default_factory=dict)


class ChapterSceneOrderItem(DomainModel):
    scene_id: str
    scene_no: int
    accepted_draft_id: str


class ChapterBasicStats(DomainModel):
    scene_count: int = 0
    accepted_scene_count: int = 0
    character_count: int = 0
    paragraph_count: int = 0
    char_count: int = 0


class ChapterAssembledDocument(DomainModel):
    project_id: str
    volume_id: str
    chapter_id: str
    chapter_no: int
    version: int = 0
    status: str = "assembled"
    updated_at: datetime
    source_versions: ChapterAssembledSourceVersions = Field(default_factory=ChapterAssembledSourceVersions)
    scene_order: list[ChapterSceneOrderItem] = Field(default_factory=list)
    content_md: str = ""
    summary: str = ""
    hook: str = ""
    basic_stats: ChapterBasicStats = Field(default_factory=ChapterBasicStats)
    latest_check_report_path: str | None = None
    last_check_status: str | None = None
    last_check_blocker_count: int = 0
    last_check_warning_count: int = 0
    finalized_at: datetime | None = None
    finalized_from_assembly_version: int | None = None


class VolumeAssembledSourceVersions(DomainModel):
    volume_version: int = 0
    planned_chapter_versions: dict[str, int] = Field(default_factory=dict)
    finalized_chapter_versions: dict[str, int] = Field(default_factory=dict)


class VolumeChapterOrderItem(DomainModel):
    chapter_id: str
    chapter_no: int
    assembled_version: int


class VolumeProgressStats(DomainModel):
    planned_chapter_count: int = 0
    finalized_chapter_count: int = 0
    completion_ratio: float = 0.0
    scene_count_total: int = 0
    paragraph_count_total: int = 0
    char_count_total: int = 0
    first_finalized_chapter_no: int | None = None
    last_finalized_chapter_no: int | None = None


class VolumeAssembledDocument(DomainModel):
    project_id: str
    volume_id: str
    volume_no: int
    version: int = 0
    status: str = "assembled"
    updated_at: datetime
    source_versions: VolumeAssembledSourceVersions = Field(default_factory=VolumeAssembledSourceVersions)
    planned_chapter_order: list[str] = Field(default_factory=list)
    chapter_order: list[VolumeChapterOrderItem] = Field(default_factory=list)
    content_md: str = ""
    summary: str = ""
    hook: str = ""
    progress_stats: VolumeProgressStats = Field(default_factory=VolumeProgressStats)
    latest_check_report_path: str | None = None
    last_check_status: str | None = None
    last_check_blocker_count: int = 0
    last_check_warning_count: int = 0
    finalized_at: datetime | None = None
    finalized_from_assembly_version: int | None = None


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
    repair_metadata: RepairMetadata | None = None
    context_bundle_id: str | None = None
    context_bundle_path: str | None = None
    draft_path: str | None = None
    latest_check_report_path: str | None = None
    latest_check_run_id: str | None = None
    last_check_status: str | None = None
    last_check_blocker_count: int = 0
    last_check_warning_count: int = 0
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


class VolumeSummaryMemoryItem(DomainModel):
    volume_id: str
    volume_no: int
    title: str = ""
    summary: str = ""
    hook: str = ""
    planned_chapter_count: int = 0
    finalized_chapter_count: int = 0
    finalized_chapter_ids: list[str] = Field(default_factory=list)
    updated_at: datetime


class VolumeSummariesMemoryDocument(DomainModel):
    project_id: str
    version: int = 1
    updated_at: datetime
    items: list[VolumeSummaryMemoryItem] = Field(default_factory=list)


class BookAssembledSourceVersions(DomainModel):
    master_outline_version: int = 0
    planned_volume_versions: dict[str, int] = Field(default_factory=dict)
    finalized_volume_versions: dict[str, int] = Field(default_factory=dict)


class BookVolumeOrderItem(DomainModel):
    volume_id: str
    volume_no: int
    assembled_version: int


class BookProgressStats(DomainModel):
    planned_volume_count: int = 0
    finalized_volume_count: int = 0
    completion_ratio: float = 0.0
    chapter_count_total: int = 0
    scene_count_total: int = 0
    paragraph_count_total: int = 0
    char_count_total: int = 0
    first_finalized_volume_no: int | None = None
    last_finalized_volume_no: int | None = None


class BookAssembledDocument(DomainModel):
    project_id: str
    version: int = 0
    status: str = "assembled"
    updated_at: datetime
    source_versions: BookAssembledSourceVersions = Field(default_factory=BookAssembledSourceVersions)
    planned_volume_order: list[str] = Field(default_factory=list)
    volume_order: list[BookVolumeOrderItem] = Field(default_factory=list)
    content_md: str = ""
    summary: str = ""
    hook: str = ""
    progress_stats: BookProgressStats = Field(default_factory=BookProgressStats)
    latest_check_report_path: str | None = None
    last_check_status: str | None = None
    last_check_blocker_count: int = 0
    last_check_warning_count: int = 0
    latest_continuity_check_report_path: str | None = None
    last_continuity_check_status: str | None = None
    last_continuity_check_blocker_count: int = 0
    last_continuity_check_warning_count: int = 0
    finalized_at: datetime | None = None
    finalized_from_assembly_version: int | None = None


class BookSummaryMemoryDocument(DomainModel):
    project_id: str
    version: int = 1
    updated_at: datetime
    summary: str = ""
    hook: str = ""
    planned_volume_count: int = 0
    finalized_volume_count: int = 0
    finalized_volume_ids: list[str] = Field(default_factory=list)


class ExportPackageManifest(DomainModel):
    export_id: str
    scope: str
    target_id: str
    format: str
    created_at: datetime
    source_status: str
    included_files: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class ExportResult(ExportPackageManifest):
    relative_dir: str
    relative_package_path: str


class RebuildStepResult(DomainModel):
    target: str
    status: str
    created_count: int = 0
    updated_count: int = 0
    skipped_count: int = 0
    stale_count: int = 0
    details: list[str] = Field(default_factory=list)


class RebuildReport(DomainModel):
    project_id: str
    started_at: datetime
    finished_at: datetime
    targets: list[str] = Field(default_factory=list)
    overall_status: str
    steps: list[RebuildStepResult] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class ProjectHealthBibleStatus(DomainModel):
    story_bible_status: str = "missing"
    characters_status: str = "missing"
    world_status: str = "missing"
    power_system_status: str = "missing"


class ProjectHealthPlannerCounts(DomainModel):
    volumes_ready: int = 0
    chapters_ready: int = 0
    scenes_ready: int = 0
    volumes_stale: int = 0
    chapters_stale: int = 0
    scenes_stale: int = 0


class ProjectHealthScenePipeline(DomainModel):
    planned_scene_count: int = 0
    accepted_scene_count: int = 0
    missing_accepted_scene_count: int = 0
    duplicate_accepted_scene_count: int = 0
    blocked_scene_check_count: int = 0


class ProjectHealthArtifactSummary(DomainModel):
    assembled_count: int = 0
    finalized_count: int = 0
    stale_count: int = 0
    missing_count: int = 0
    blocked_count: int = 0


class ProjectHealthBookArtifact(DomainModel):
    status: str = "missing"
    blocked: bool = False


class ProjectHealthMemoryStatus(DomainModel):
    accepted_scenes_exists: bool = False
    chapter_summaries_exists: bool = False
    character_state_summaries_exists: bool = False
    volume_summaries_exists: bool = False
    book_summary_exists: bool = False


class ProjectHealthActionableItem(DomainModel):
    severity: str
    code: str
    scope: str
    target_id: str | None = None
    summary: str


class ProjectHealthReport(DomainModel):
    project_id: str
    generated_at: datetime
    overall_status: str
    bible: ProjectHealthBibleStatus = Field(default_factory=ProjectHealthBibleStatus)
    planner_counts: ProjectHealthPlannerCounts = Field(default_factory=ProjectHealthPlannerCounts)
    scene_pipeline: ProjectHealthScenePipeline = Field(default_factory=ProjectHealthScenePipeline)
    chapter_artifacts: ProjectHealthArtifactSummary = Field(default_factory=ProjectHealthArtifactSummary)
    volume_artifacts: ProjectHealthArtifactSummary = Field(default_factory=ProjectHealthArtifactSummary)
    book_artifact: ProjectHealthBookArtifact = Field(default_factory=ProjectHealthBookArtifact)
    memory: ProjectHealthMemoryStatus = Field(default_factory=ProjectHealthMemoryStatus)
    actionable_items: list[ProjectHealthActionableItem] = Field(default_factory=list)


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
