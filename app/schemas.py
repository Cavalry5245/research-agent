from pydantic import BaseModel


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


class SourceItem(BaseModel):
    paper_id: str
    title: str
    section: str
    chunk_id: str
    content: str


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


class CompareRequest(BaseModel):
    paper_ids: list[str]


class CompareResponse(BaseModel):
    paper_ids: list[str]
    status: str
    output_path: str
    content: str
