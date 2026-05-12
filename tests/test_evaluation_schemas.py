import os
import sys

import pytest
from pydantic import ValidationError

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.evaluation.schemas import (
    ComparisonEvalSample,
    QAEvalSample,
    RetrievalEvalResult,
    RetrievalMatch,
)


def test_qa_eval_sample_schema_accepts_required_fields():
    sample = QAEvalSample(
        sample_id="qa-001",
        question="What is the core method?",
        expected_answer="A transformer-based detector.",
        paper_id="paper-123",
        paper_title="Example Paper",
        supporting_sections=["Method", "Experiments"],
        difficulty="medium",
        metadata={"source": "seed"},
    )

    assert sample.sample_id == "qa-001"
    assert sample.supporting_sections == ["Method", "Experiments"]
    assert sample.difficulty == "medium"
    assert sample.metadata == {"source": "seed"}


@pytest.mark.parametrize(
    "payload,expected_field",
    [
        ({"question": "Missing identifiers", "expected_answer": "x"}, "sample_id"),
        (
            {
                "sample_id": "qa-002",
                "question": "What is missing?",
                "expected_answer": "Answer",
                "supporting_sections": "Method",
            },
            "supporting_sections",
        ),
    ],
)
def test_qa_eval_sample_schema_validates_required_structure(payload, expected_field):
    with pytest.raises(ValidationError) as exc_info:
        QAEvalSample(**payload)

    assert expected_field in str(exc_info.value)


def test_comparison_eval_sample_schema_supports_multi_paper_gold_data():
    sample = ComparisonEvalSample(
        sample_id="cmp-001",
        question="How do the methods differ?",
        paper_ids=["paper-a", "paper-b"],
        paper_titles=["Paper A", "Paper B"],
        expected_summary="Paper A uses CNNs, while Paper B uses transformers.",
        comparison_aspects=["model_architecture", "performance"],
        supporting_sections={
            "paper-a": ["Method"],
            "paper-b": ["Method", "Results"],
        },
        metadata={"source": "seed"},
    )

    assert sample.paper_ids == ["paper-a", "paper-b"]
    assert sample.supporting_sections["paper-b"] == ["Method", "Results"]


def test_comparison_eval_sample_rejects_mismatched_titles_and_ids():
    with pytest.raises(ValidationError) as exc_info:
        ComparisonEvalSample(
            sample_id="cmp-002",
            question="Compare the papers",
            paper_ids=["paper-a", "paper-b"],
            paper_titles=["Paper A"],
            expected_summary="summary",
            comparison_aspects=["dataset"],
            supporting_sections={"paper-a": ["Method"], "paper-b": ["Results"]},
        )

    assert "paper_titles" in str(exc_info.value)


def test_retrieval_eval_result_schema_tracks_metrics_and_ranked_matches():
    result = RetrievalEvalResult(
        sample_id="qa-001",
        query="What is the core method?",
        top_k=5,
        hit_at_k=True,
        recall_at_k=1.0,
        mrr=0.5,
        retrieved_chunks=[
            RetrievalMatch(
                chunk_id="chunk-1",
                paper_id="paper-123",
                section="Abstract",
                score=0.91,
                rank=1,
                is_relevant=False,
            ),
            RetrievalMatch(
                chunk_id="chunk-2",
                paper_id="paper-123",
                section="Method",
                score=0.89,
                rank=2,
                is_relevant=True,
            ),
        ],
    )

    assert result.hit_at_k is True
    assert result.retrieved_chunks[1].is_relevant is True
    assert result.retrieved_chunks[1].rank == 2


def test_retrieval_eval_result_validates_metric_ranges():
    with pytest.raises(ValidationError) as exc_info:
        RetrievalEvalResult(
            sample_id="qa-003",
            query="Invalid metric example",
            top_k=3,
            hit_at_k=False,
            recall_at_k=1.5,
            mrr=-0.1,
            retrieved_chunks=[],
        )

    error_text = str(exc_info.value)
    assert "recall_at_k" in error_text
    assert "mrr" in error_text
