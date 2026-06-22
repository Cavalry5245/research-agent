"""
Research Pipeline Schemas

定义 research pipeline 的数据模型。
"""

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


# ==================== Enums and Literals ====================

SourceMode = Literal["web_search", "zotero_only", "hybrid"]
RunStatus = Literal["queued", "running", "completed", "failed", "cancelled", "degraded"]
StageStatus = Literal["queued", "running", "completed", "failed", "degraded"]
StageName = Literal["planner", "retriever", "reader", "synthesis", "harness"]
EventStageName = Literal["planner", "retriever", "reader", "synthesis", "harness", "runner"]
VerificationStatus = Literal[
    "supported",
    "weak",
    "unverified",
    "numeric_trace_missing",
    "conflict_detected",
]
ClaimType = Literal["method", "dataset", "metric", "result", "limitation", "gap", "other"]
ExtractionMode = Literal["pdf", "abstract_only"]
EventLevel = Literal["debug", "info", "warning", "error"]
PlanPhase = Literal["initial", "candidate_selection"]


# ==================== Request Schemas ====================


class ResearchRunCreateRequest(BaseModel):
    """创建研究运行请求"""

    question: str
    source_mode: SourceMode = "hybrid"
    zotero_collection_key: str | None = None
    max_reader_papers: int = Field(default=8, ge=3, le=15)
    reader_concurrency: int = 3
    year_start: int | None = None
    year_end: int | None = None
    venue_filter: list[str] = Field(default_factory=list)
    keywords: list[str] = Field(default_factory=list)


# ==================== Response Schemas ====================


class ResearchRunCreateResponse(BaseModel):
    """创建研究运行响应"""

    run_id: str
    status: RunStatus
    created_at: datetime


class ResearchRunSummary(BaseModel):
    """研究运行摘要（用于列表视图）"""

    run_id: str
    question: str
    source_mode: SourceMode
    status: RunStatus
    error: str | None = None
    created_at: datetime


class ResearchRunListResponse(BaseModel):
    """研究运行列表响应"""

    count: int
    runs: list[ResearchRunSummary]


class ResearchRunDetailResponse(BaseModel):
    """研究运行详情响应"""

    run_id: str
    question: str
    normalized_question: str | None = None
    source_mode: SourceMode
    zotero_collection_key: str | None = None
    status: RunStatus
    max_reader_papers: int
    reader_concurrency: int
    year_start: int | None = None
    year_end: int | None = None
    venue_filter: list[str] = Field(default_factory=list)
    keywords: list[str] = Field(default_factory=list)
    created_at: datetime
    started_at: datetime | None = None
    completed_at: datetime | None = None
    failed_at: datetime | None = None
    cancelled_at: datetime | None = None
    error: str | None = None
    stages: list["ResearchStage"]
    events: list["ResearchEvent"]
    candidates: list["PaperCandidate"]
    cards: list["PaperCard"]
    plan: "ResearchPlan | None" = None
    report: "ResearchReport | None" = None


# ==================== Core Data Models ====================


class PaperCandidate(BaseModel):
    """候选论文"""

    paper_id: str
    source: Literal["semantic_scholar", "arxiv", "zotero"]
    title: str
    authors: list[str] = Field(default_factory=list)
    year: int | None = None
    venue: str | None = None
    abstract: str | None = None
    doi: str | None = None
    arxiv_id: str | None = None
    semantic_scholar_id: str | None = None
    zotero_item_id: str | None = None
    url: str | None = None
    pdf_url: str | None = None
    local_pdf_path: str | None = None
    citation_count: int | None = None
    relevance_score: float | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class PaperCard(BaseModel):
    """论文卡片（提取后的结构化信息）"""

    paper_id: str
    status: StageStatus
    extraction_mode: ExtractionMode
    title: str
    bibliographic_metadata: dict[str, Any] = Field(default_factory=dict)
    research_problem: str = ""
    method: str = ""
    datasets: list[str] = Field(default_factory=list)
    metrics: list[str] = Field(default_factory=list)
    key_results: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    future_work: list[str] = Field(default_factory=list)
    claims: list[dict[str, Any]] = Field(default_factory=list)
    evidence: list[dict[str, Any]] = Field(default_factory=list)
    error: str | None = None


class ReportClaim(BaseModel):
    """报告声明"""

    claim_text: str
    claim_type: ClaimType
    citation_ids: list[str] = Field(default_factory=list)
    evidence_ids: list[str] = Field(default_factory=list)
    verification_status: VerificationStatus
    verification_reason: str = ""


class ResearchPlan(BaseModel):
    """研究计划"""

    id: str
    run_id: str
    version: int
    phase: PlanPhase
    plan_data: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime


class ResearchStage(BaseModel):
    """研究阶段"""

    id: str
    run_id: str
    stage: StageName
    status: StageStatus
    progress: float = 0.0
    message: str = ""
    started_at: datetime | None = None
    completed_at: datetime | None = None
    error: str | None = None
    created_at: datetime


class ResearchEvent(BaseModel):
    """研究事件"""

    id: str
    run_id: str
    stage: EventStageName
    level: EventLevel
    message: str
    payload: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime


class ResearchReport(BaseModel):
    """研究报告"""

    id: str
    run_id: str
    status: str
    markdown: str
    template_version: str
    created_at: datetime
    updated_at: datetime


class ReportWithClaimsResponse(BaseModel):
    """Report with claims and summary response"""

    markdown: str
    claims: list[ReportClaim]
    summary: dict[str, int]
