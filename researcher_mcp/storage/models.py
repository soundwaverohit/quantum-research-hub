"""Pydantic v2 models for every persisted entity + the paper card schema.

These mirror the SQLite schema (ARCHITECTURE.md §8) and the paper-card JSON
schema (§5.3). They are the single source of truth for shapes that move
between the DB, the MCP tools, the agents, and the dashboard.
"""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


# --- Enums --------------------------------------------------------------------
class RecommendedAction(str, Enum):
    IGNORE = "ignore"
    TRACK = "track"
    SUMMARIZE = "summarize"
    REPRODUCE = "reproduce"
    EXTEND = "extend"


class PaperStatus(str, Enum):
    DISCOVERED = "discovered"
    INGESTED = "ingested"
    CARDED = "carded"
    CURATED = "curated"


class IdeaStatus(str, Enum):
    PROPOSED = "proposed"
    PROMOTED = "promoted"      # turned into an experiment
    ARCHIVED = "archived"


class ExperimentStatus(str, Enum):
    PROPOSED = "proposed"
    APPROVED = "approved"
    BUILDING = "building"
    RUNNING = "running"
    FAILED = "failed"
    VALIDATED = "validated"
    REJECTED = "rejected"
    ARCHIVED = "archived"


class ValidatorVerdict(str, Enum):
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    INCONCLUSIVE = "inconclusive"


# --- Persisted entities -------------------------------------------------------
class Paper(BaseModel):
    arxiv_id: str
    title: str
    authors: list[str] = Field(default_factory=list)
    abstract: str = ""
    categories: list[str] = Field(default_factory=list)
    published_date: str | None = None
    updated_date: str | None = None
    pdf_url: str | None = None
    pdf_path: str | None = None
    parsed_text_path: str | None = None
    paper_card_path: str | None = None
    relevance_score: float = 0.0
    novelty_score: float = 0.0
    implementation_score: float = 0.0
    recommended_action: RecommendedAction = RecommendedAction.TRACK
    status: PaperStatus = PaperStatus.DISCOVERED
    created_at: str | None = None
    updated_at: str | None = None


class PaperChunk(BaseModel):
    id: int | None = None
    arxiv_id: str
    section: str | None = None
    chunk_index: int = 0
    chunk_text: str
    token_estimate: int = 0
    embedding_id: str | None = None


class PaperCard(BaseModel):
    """Compact, Claude-sized representation of a paper (ARCHITECTURE.md §5.3)."""

    arxiv_id: str
    title: str
    authors: list[str] = Field(default_factory=list)
    published: str | None = None
    categories: list[str] = Field(default_factory=list)
    abstract: str = ""
    core_contribution: str = ""
    methods: list[str] = Field(default_factory=list)
    claims: list[str] = Field(default_factory=list)
    datasets_or_benchmarks: list[str] = Field(default_factory=list)
    relevance_to_user: str = ""
    possible_experiments: list[str] = Field(default_factory=list)
    matched_keyword_groups: list[str] = Field(default_factory=list)
    relevance_score: float = 0.0
    novelty_score: float = 0.0
    implementation_difficulty: float = 0.0
    recommended_action: RecommendedAction = RecommendedAction.TRACK
    generated_by: str = "deterministic"  # "deterministic" | "model"
    # Synthesis engine fields (optional; populated during ingestion)
    concept_terms: list[str] = Field(default_factory=list)      # human-readable concept names
    concept_relations: list[dict] = Field(default_factory=list) # [{source, target, relation, weight}]


class Concept(BaseModel):
    name: str
    concept_type: str
    description: str = ""
    aliases: list[str] = Field(default_factory=list)
    paper_count: int = 0


class ConceptEdge(BaseModel):
    source: str
    target: str
    relation: str
    weight: float = 1.0
    paper_ids: list[str] = Field(default_factory=list)


class Idea(BaseModel):
    id: str
    title: str
    hypothesis: str
    source_arxiv_ids: list[str] = Field(default_factory=list)
    observation: str = ""
    why_it_might_work: str = ""
    smallest_experiment: str = ""
    baseline: str = ""
    metric: str = ""
    failure_modes: list[str] = Field(default_factory=list)
    expected_runtime: str = ""
    novelty_score: float = 0.0
    feasibility_score: float = 0.0
    expected_compute_cost: str = "small"
    status: IdeaStatus = IdeaStatus.PROPOSED
    idea_card_path: str | None = None
    created_at: str | None = None
    updated_at: str | None = None


class Experiment(BaseModel):
    id: str
    idea_id: str | None = None
    title: str
    hypothesis: str = ""
    status: ExperimentStatus = ExperimentStatus.PROPOSED
    folder_path: str | None = None
    config_path: str | None = None
    result_path: str | None = None
    validator_notes_path: str | None = None
    created_at: str | None = None
    updated_at: str | None = None


class ExperimentRun(BaseModel):
    id: str
    experiment_id: str
    status: str = "created"
    started_at: str | None = None
    finished_at: str | None = None
    metrics: dict[str, Any] = Field(default_factory=dict)
    logs_path: str | None = None
    error_message: str | None = None


class AgentEvent(BaseModel):
    id: int | None = None
    timestamp: str | None = None
    agent_name: str
    action: str
    input_summary: str = ""
    output_summary: str = ""
    status: str = "ok"
    cost_estimate: dict[str, Any] = Field(default_factory=dict)
    artifact_path: str | None = None


class BudgetEvent(BaseModel):
    id: int | None = None
    timestamp: str | None = None
    budget_profile: str = "low"
    event_type: str = ""
    estimated_tokens: int = 0
    estimated_cost: float = 0.0
    local_runtime_seconds: float = 0.0
    notes: str = ""
