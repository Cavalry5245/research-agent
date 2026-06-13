from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator


class HealthResponse(BaseModel):
    status: str
    project: str
    storage_writable: bool | None = None
    vector_store_available: bool | None = None
    config: dict[str, bool] = Field(default_factory=dict)


class ErrorResponse(BaseModel):
    error: str
    message: str
    request_id: str | None = None
    status_code: int


class DeletePaperResponse(BaseModel):
    paper_id: str
    status: str
    deleted_files: list[str]
    deleted_chunks: int


class PaperIndexSummary(BaseModel):
    paper_id: str
    chunk_count: int
    sections: list[str]


class PaperIndexDetailResponse(BaseModel):
    paper_id: str
    indexed: bool
    chunk_count: int
    sections: list[str]


class LibraryIndexStatusResponse(BaseModel):
    total_chunks: int
    paper_count: int
    papers: list[PaperIndexSummary]


class Section(BaseModel):
    heading: str
    content: str
    page_number: int | None = None


class PaperParseResult(BaseModel):
    paper_id: str
    title: str
    abstract: str
    sections: list[Section]
    full_text: str
    pdf_path: str = ""


class PaperUploadResponse(BaseModel):
    paper_id: str
    filename: str
    status: str
    storage_path: str


class ParseStatusResponse(BaseModel):
    paper_id: str
    status: str
    json_path: str


class NoteGenerateResponse(BaseModel):
    paper_id: str
    status: str
    note_path: str
    content: str


class NoteStatusResponse(BaseModel):
    paper_id: str
    status: str
    note_path: str


class Chunk(BaseModel):
    chunk_id: str
    paper_id: str
    title: str
    section: str
    content: str
    page_number: int | None = None
    chunk_start: int | None = None
    chunk_end: int | None = None
    # Parent-child architecture fields (optional for backward compatibility)
    parent_id: str | None = None
    section_path: str | None = None
    page_range: str | None = None
    element_type: str | None = None
    content_for_embedding: str | None = None
    context_header: str | None = None


class NoteReadResponse(BaseModel):
    paper_id: str
    note_path: str
    content: str


class PaperListItem(BaseModel):
    paper_id: str
    title: str
    abstract: str


class PaperListResponse(BaseModel):
    count: int
    papers: list[PaperListItem]


class RetrievalResult(BaseModel):
    chunk_id: str
    content: str
    paper_id: str
    title: str
    section: str
    score: float
    rerank_score: float | None = None


class SourceItem(BaseModel):
    paper_id: str
    title: str
    section: str
    chunk_id: str
    content: str
    score: float | None = None
    page_number: int | None = None
    chunk_start: int | None = None
    chunk_end: int | None = None
    # Parent-child architecture fields (optional for backward compatibility)
    parent_id: str | None = None
    page_range: str | None = None
    section_path: str | None = None
    element_type: str | None = None
    citation_label: str | None = None


class QARequest(BaseModel):
    question: str
    paper_id: str | None = None
    top_k: int = 5


class QAResponse(BaseModel):
    question: str
    answer: str
    sources: list[SourceItem]


class JobStatusResponse(BaseModel):
    job_id: str
    job_type: Literal[
        "paper_index", "note_generation", "paper_comparison", "batch_index"
    ]
    status: Literal["queued", "running", "completed", "failed", "cancelled"]
    progress: float = Field(default=0.0, ge=0.0, le=1.0)
    paper_id: str | None = None
    paper_ids: list[str] = Field(default_factory=list)
    result: dict[str, Any] | None = None
    error: str | None = None
    retry_of: str | None = None
    created_at: datetime
    started_at: datetime | None = None
    completed_at: datetime | None = None
    updated_at: datetime

    @model_validator(mode="after")
    def validate_lifecycle_timestamps(self):
        if self.status == "queued" and self.started_at is not None:
            raise ValueError("queued 状态不得提供 started_at")
        if self.status == "running" and self.started_at is None:
            raise ValueError("running 状态必须提供 started_at")
        if self.status == "running" and self.completed_at is not None:
            raise ValueError("running 状态不得提供 completed_at")
        if self.status in {"completed", "cancelled"} and self.completed_at is None:
            raise ValueError("completed/cancelled 状态必须提供 completed_at")
        if self.status == "failed" and self.completed_at is not None:
            raise ValueError("failed 状态不得提供 completed_at")
        if self.completed_at is not None and self.started_at is None:
            raise ValueError(
                "completed/cancelled 状态提供 completed_at 时必须同时提供 started_at"
            )
        if (
            self.completed_at is not None
            and self.started_at is not None
            and self.completed_at < self.started_at
        ):
            raise ValueError("completed_at 不得早于 started_at")
        if self.updated_at < self.created_at:
            raise ValueError("updated_at 不得早于 created_at")
        if self.started_at is not None and self.started_at < self.created_at:
            raise ValueError("started_at 不得早于 created_at")
        if self.completed_at is not None and self.updated_at < self.completed_at:
            raise ValueError("updated_at 不得早于 completed_at")
        if self.status == "failed" and self.error and self.started_at is None:
            raise ValueError("failed 状态提供 error 时必须同时提供 started_at")
        if (
            self.status == "failed"
            and self.progress == 0.0
            and self.started_at is not None
            and self.completed_at is None
            and self.error is None
        ):
            raise ValueError(
                "failed 状态在 progress = 0、completed_at 缺失且 error 为空时不得提供 started_at"
            )
        return self


class IndexStatusResponse(JobStatusResponse):
    job_type: Literal["paper_index"] = "paper_index"
    paper_id: str
    chunks_indexed: int
    already_indexed: bool = False
    parse_seconds: float = 0.0
    chunk_seconds: float = 0.0
    embedding_seconds: float = 0.0
    persist_seconds: float = 0.0
    total_seconds: float = 0.0


class IndexJobStatusResponse(IndexStatusResponse):
    pass


class JobListResponse(BaseModel):
    count: int
    jobs: list[JobStatusResponse] = Field(default_factory=list)


class JobRetryResponse(BaseModel):
    original_job_id: str
    retry_job: JobStatusResponse


class CompareRequest(BaseModel):
    paper_ids: list[str]


class PaperEvidence(BaseModel):
    paper_id: str
    paper_title: str
    section: str
    snippet: str


class PaperStructuredSummary(BaseModel):
    paper_id: str
    paper_title: str
    research_problem: str = "未明确说明"
    method: str = "未明确说明"
    backbone: str = "未明确说明"
    dataset: str = "未明确说明"
    metrics: str = "未明确说明"
    strengths: str = "未明确说明"
    limitations: str = "未明确说明"
    scenarios: str = "未明确说明"
    evidence: list[PaperEvidence] = Field(default_factory=list)


class CompareAspect(BaseModel):
    name: str
    summary: str
    key_differences: list[str] = Field(default_factory=list)
    per_paper: dict[str, str] = Field(default_factory=dict)
    evidence: list[PaperEvidence] = Field(default_factory=list)


class PaperComparisonResult(BaseModel):
    overview: str
    aspects: list[CompareAspect]
    markdown: str
    structured_summaries: dict[str, PaperStructuredSummary] | None = None


class CompareBatchSampleResult(BaseModel):
    sample_id: str
    question: str
    paper_ids: list[str]
    comparison: PaperComparisonResult


class CompareBatchRunResult(BaseModel):
    dataset_path: str
    total_samples: int
    generated_at: str
    results: list[CompareBatchSampleResult]


class CompareResponse(BaseModel):
    paper_ids: list[str]
    status: str
    output_path: str
    content: str
    comparison: PaperComparisonResult | None = None


class AgentChatMessage(BaseModel):
    role: str
    content: str


class AgentExecuteRequest(BaseModel):
    task: str
    chat_history: list[AgentChatMessage] | None = None
    mode: str = "react"  # "react" (LangChain ReAct) or "supervisor" (multi-agent)
    conversation_id: str | None = None
    context: dict | None = None


class AgentExecuteResponse(BaseModel):
    task: str
    answer: str
    conversation_id: str | None = None
    task_type: str | None = None


class KBCreateRequest(BaseModel):
    kb_id: str
    name: str
    description: str = ""


class KBResponse(BaseModel):
    id: str
    name: str
    description: str = ""
    paper_ids: list[str] = []
    created_at: str | None = None


class KBListResponse(BaseModel):
    count: int
    knowledge_bases: list[KBResponse]


class KBAddPaperRequest(BaseModel):
    paper_id: str


# ==================== Parent-Child Document Architecture Models ====================


class PdfProfile(BaseModel):
    """PDF 类型和版式识别结果"""

    paper_id: str
    page_count: int
    is_text_pdf: bool  # 是否为文本型 PDF（非扫描版）
    layout_type: Literal["single_column", "double_column", "mixed", "unknown"]
    text_density: float  # 平均每页字符数
    has_tables: bool
    has_figures: bool
    reference_page_start: int | None = None  # 参考文献起始页
    warnings: list[str] = Field(default_factory=list)  # 解析警告


class DocumentElement(BaseModel):
    """结构化解析的最小元素"""

    element_id: str
    paper_id: str
    type: Literal[
        "title",
        "abstract",
        "heading",
        "paragraph",
        "table",
        "figure_caption",
        "equation",
        "reference",
    ]
    text: str
    page_number: int
    bbox: tuple[float, float, float, float] | None = None  # (x0, y0, x1, y1)
    section_path: str | None = None  # e.g., "Introduction/Background"
    order_index: int  # 阅读顺序
    metadata: dict[str, Any] = Field(default_factory=dict)


class ParentDocument(BaseModel):
    """父文档保存完整上下文"""

    parent_id: str
    paper_id: str
    title: str  # 论文标题
    section_path: str | None = None  # 章节路径
    content: str  # 完整内容
    page_range: str | None = None  # e.g., "3-5"
    element_type: Literal["abstract", "section", "table", "figure", "mixed"] = "section"
    element_ids: list[str] = Field(default_factory=list)  # 包含的元素 ID
    bbox_refs: list[tuple[int, tuple[float, float, float, float]]] = Field(
        default_factory=list
    )  # [(page, bbox), ...]
    metadata: dict[str, Any] = Field(default_factory=dict)

