from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field, model_validator


class QAEvalSample(BaseModel):
    sample_id: str
    question: str
    expected_answer: str
    paper_id: str | None = None
    paper_title: str | None = None
    supporting_sections: list[str] = Field(default_factory=list)
    difficulty: str = "medium"
    metadata: dict[str, Any] = Field(default_factory=dict)


class ComparisonEvalSample(BaseModel):
    sample_id: str
    question: str
    paper_ids: list[str]
    paper_titles: list[str]
    expected_summary: str
    comparison_aspects: list[str] = Field(default_factory=list)
    supporting_sections: dict[str, list[str]] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_paper_alignment(self) -> "ComparisonEvalSample":
        if len(self.paper_ids) != len(self.paper_titles):
            raise ValueError("paper_titles must align with paper_ids")
        return self


class RetrievalMatch(BaseModel):
    chunk_id: str
    paper_id: str
    section: str
    score: float
    rank: int = Field(ge=1)
    is_relevant: bool


class RetrievalEvalResult(BaseModel):
    sample_id: str
    query: str
    top_k: int = Field(ge=1)
    hit_at_k: bool
    recall_at_k: float = Field(ge=0.0, le=1.0)
    mrr: float = Field(ge=0.0, le=1.0)
    retrieved_chunks: list[RetrievalMatch] = Field(default_factory=list)
