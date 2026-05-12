from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    status: str
    project: str


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


class QARequest(BaseModel):
    question: str
    paper_id: str | None = None
    top_k: int = 5


class QAResponse(BaseModel):
    question: str
    answer: str
    sources: list[SourceItem]


class IndexStatusResponse(BaseModel):
    paper_id: str
    status: str
    chunks_indexed: int
    already_indexed: bool = False
    parse_seconds: float = 0.0
    chunk_seconds: float = 0.0
    embedding_seconds: float = 0.0
    persist_seconds: float = 0.0
    total_seconds: float = 0.0


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
