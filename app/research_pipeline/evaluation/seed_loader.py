"""
Seed Evaluation Dataset Loader

加载和验证 research pipeline 的 gold annotation 数据集。
"""

import json
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field, field_validator, model_validator


class GoldPaper(BaseModel):
    """Gold standard paper annotation"""

    title: str
    doi: str | None = None
    arxiv_id: str | None = None
    semantic_scholar_id: str | None = None
    relevance: int = Field(ge=1, le=3)
    reason: str

    @field_validator("relevance")
    @classmethod
    def validate_relevance(cls, v: int) -> int:
        """Validate relevance score is 1-3"""
        if v < 1 or v > 3:
            raise ValueError("relevance must be between 1 and 3")
        return v

    @model_validator(mode="after")
    def validate_identifiers(self) -> "GoldPaper":
        """Validate at least one paper identifier is present"""
        if not any([self.doi, self.arxiv_id, self.semantic_scholar_id]):
            raise ValueError(
                "At least one of doi, arxiv_id, or semantic_scholar_id must be provided"
            )
        return self


class GoldReportPoint(BaseModel):
    """Gold standard report point annotation"""

    point: str
    expected_section: str
    required_papers: list[str] = Field(default_factory=list)

    @field_validator("expected_section")
    @classmethod
    def validate_section(cls, v: str) -> str:
        """Validate expected_section is one of allowed values"""
        valid_sections = {
            "method_comparison",
            "dataset_metrics",
            "gap",
            "limitation",
            "background",
            "results",
            "future_work",
        }
        if v not in valid_sections:
            raise ValueError(
                f"expected_section must be one of {valid_sections}, got {v}"
            )
        return v


class GoldClaim(BaseModel):
    """Gold standard claim annotation"""

    claim: str
    paper_id: str
    evidence_snippet: str
    page: int | None = None
    section: str | None = None
    numeric: bool = False


class SeedQuestion(BaseModel):
    """Seed research question with gold annotations"""

    question: str
    gold_papers: list[GoldPaper] = Field(min_length=5)
    gold_report_points: list[GoldReportPoint] = Field(min_length=5)
    gold_claims: list[GoldClaim] = Field(min_length=5)

    @field_validator("question")
    @classmethod
    def validate_question(cls, v: str) -> str:
        """Validate question is not empty"""
        if not v.strip():
            raise ValueError("question cannot be empty")
        return v.strip()


class SeedDataset(BaseModel):
    """Seed evaluation dataset container"""

    questions: list[SeedQuestion] = Field(min_length=3)
    metadata: dict[str, Any] = Field(default_factory=dict)


def load_seed_dataset(jsonl_path: str | Path) -> SeedDataset:
    """
    从 JSONL 文件加载 seed dataset。

    Args:
        jsonl_path: JSONL 文件路径

    Returns:
        SeedDataset 实例

    Raises:
        FileNotFoundError: 文件不存在
        ValueError: 数据格式错误或验证失败
        json.JSONDecodeError: JSON 解析失败
    """
    path = Path(jsonl_path)
    if not path.exists():
        raise FileNotFoundError(f"Dataset file not found: {jsonl_path}")

    questions = []
    line_number = 0

    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line_number += 1
            line = line.strip()
            if not line:
                continue

            try:
                data = json.loads(line)
                question = SeedQuestion(**data)
                questions.append(question)
            except json.JSONDecodeError as e:
                raise json.JSONDecodeError(
                    f"Invalid JSON at line {line_number}: {e.msg}",
                    e.doc,
                    e.pos,
                ) from e
            except ValueError as e:
                raise ValueError(
                    f"Validation error at line {line_number}: {str(e)}"
                ) from e

    if len(questions) < 3:
        raise ValueError(
            f"Dataset must contain at least 3 questions, found {len(questions)}"
        )

    return SeedDataset(questions=questions)
