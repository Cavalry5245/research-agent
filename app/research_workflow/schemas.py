from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


ResearchRunStatus = Literal["queued", "running", "completed", "failed", "cancelled"]

DEFAULT_RESEARCH_RUN_STEPS = [
    ("collection_intake", "CollectionIntakeAgent"),
    ("paper_understanding", "PaperUnderstandingAgent"),
    ("literature_synthesis", "LiteratureSynthesisAgent"),
    ("experiment_planning", "ExperimentPlanningAgent"),
    ("obsidian_publishing", "ObsidianPublishingAgent"),
]


class ResearchRunOptions(BaseModel):
    semantic_scholar: bool = False
    arxiv: bool = False
    obsidian_publish: bool = False
    max_papers: int = Field(default=5, ge=1, le=50)
    obsidian_vault_path: str | None = None


class ResearchRunStep(BaseModel):
    step_id: str
    agent: str
    status: ResearchRunStatus = "queued"
    progress: float = Field(default=0.0, ge=0.0, le=1.0)
    message: str = ""
    started_at: datetime | None = None
    completed_at: datetime | None = None
    error: str | None = None


class ResearchRunArtifact(BaseModel):
    label: str
    path: str
    kind: Literal["markdown", "json", "jsonl", "directory"]


ResearchRunPaperStatus = Literal["queued", "running", "completed", "failed", "skipped"]


class ResearchRunPaperArtifact(BaseModel):
    label: str
    path: str
    kind: Literal["pdf", "markdown", "json", "vector_index"]


class ResearchRunPaperItem(BaseModel):
    item_id: str
    title: str
    zotero_item_id: str
    paper_id: str | None = None
    pdf_path: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    status: ResearchRunPaperStatus = "queued"
    progress: float = Field(default=0.0, ge=0.0, le=1.0)
    error: str | None = None
    artifacts: list[ResearchRunPaperArtifact] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime
    started_at: datetime | None = None
    completed_at: datetime | None = None


class ResearchRun(BaseModel):
    run_id: str
    goal: str
    source: Literal["zotero_collection"] = "zotero_collection"
    collection_id: str
    collection_name: str
    status: ResearchRunStatus = "queued"
    progress: float = Field(default=0.0, ge=0.0, le=1.0)
    options: ResearchRunOptions = Field(default_factory=ResearchRunOptions)
    steps: list[ResearchRunStep] = Field(default_factory=list)
    artifacts: list[ResearchRunArtifact] = Field(default_factory=list)
    paper_items: list[ResearchRunPaperItem] = Field(default_factory=list)
    output_dir: str = ""
    error: str | None = None
    created_at: datetime
    updated_at: datetime
    started_at: datetime | None = None
    completed_at: datetime | None = None


class ResearchRunCreateRequest(BaseModel):
    collection_id: str
    collection_name: str
    goal: str = (
        "Generate a literature review and experiment plan from this Zotero collection."
    )
    options: ResearchRunOptions = Field(default_factory=ResearchRunOptions)


class ResearchRunListResponse(BaseModel):
    count: int
    runs: list[ResearchRun]


def build_default_steps() -> list[ResearchRunStep]:
    return [
        ResearchRunStep(step_id=step_id, agent=agent)
        for step_id, agent in DEFAULT_RESEARCH_RUN_STEPS
    ]
