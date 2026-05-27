import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.evaluation.schemas import QAEvalSample

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = REPO_ROOT / "app" / "evaluation" / "scripts" / "evaluate_retrieval.py"
QA_DATASET = REPO_ROOT / "app" / "evaluation" / "datasets" / "qa_eval_seed.jsonl"
PYTHON_EXECUTABLE = sys.executable


def _build_fake_vector_store_results(sample, top_k: int = 3):
    supporting_sections = sample.supporting_sections or ["Abstract"]
    unique_sections = []
    for section in supporting_sections:
        if section not in unique_sections:
            unique_sections.append(section)
    primary_section = unique_sections[0]
    secondary_section = unique_sections[1] if len(unique_sections) > 1 else None
    return {
        "dense": [
            {
                "chunk_id": f"{sample.sample_id}-dense-distractor-1",
                "paper_id": sample.paper_id,
                "section": "Conclusion",
                "content": "Completely unrelated conclusion text.",
                "score": 0.96,
            },
            {
                "chunk_id": f"{sample.sample_id}-{primary_section.lower()}-gold-1",
                "paper_id": sample.paper_id,
                "section": primary_section,
                "content": f"Evidence for {primary_section}.",
                "score": 0.81,
            },
            {
                "chunk_id": f"{sample.sample_id}-dense-extra-distractor-2",
                "paper_id": sample.paper_id,
                "section": "Background",
                "content": "A dense retriever false positive with mild semantic overlap.",
                "score": 0.73,
            },
        ][:top_k],
        "dense_rerank": [
            {
                "chunk_id": f"{sample.sample_id}-{primary_section.lower()}-gold-1",
                "paper_id": sample.paper_id,
                "section": primary_section,
                "content": f"Evidence for {primary_section}.",
                "score": 0.98,
            },
            *(
                [
                    {
                        "chunk_id": f"{sample.sample_id}-{secondary_section.lower()}-gold-2",
                        "paper_id": sample.paper_id,
                        "section": secondary_section,
                        "content": f"Evidence for {secondary_section}.",
                        "score": 0.88,
                    }
                ]
                if secondary_section
                else [
                    {
                        "chunk_id": f"{sample.sample_id}-dense-rerank-support-2",
                        "paper_id": sample.paper_id,
                        "section": primary_section,
                        "content": f"Additional evidence for {primary_section}.",
                        "score": 0.84,
                    }
                ]
            ),
            {
                "chunk_id": f"{sample.sample_id}-dense-distractor-1",
                "paper_id": sample.paper_id,
                "section": "Conclusion",
                "content": "Completely unrelated conclusion text.",
                "score": 0.62,
            },
        ][:top_k],
        "hybrid": [
            {
                "chunk_id": f"{sample.sample_id}-{primary_section.lower()}-gold-1",
                "paper_id": sample.paper_id,
                "section": primary_section,
                "content": f"Evidence for {primary_section}.",
                "score": 0.92,
            },
            {
                "chunk_id": f"{sample.sample_id}-hybrid-distractor-1",
                "paper_id": sample.paper_id,
                "section": "Background",
                "content": "Keyword overlap but incomplete support.",
                "score": 0.79,
            },
            *(
                [
                    {
                        "chunk_id": f"{sample.sample_id}-{secondary_section.lower()}-gold-2",
                        "paper_id": sample.paper_id,
                        "section": secondary_section,
                        "content": f"Evidence for {secondary_section}.",
                        "score": 0.74,
                    }
                ]
                if secondary_section
                else []
            ),
        ][:top_k],
        "hybrid_rerank": [
            {
                "chunk_id": f"{sample.sample_id}-{primary_section.lower()}-gold-1",
                "paper_id": sample.paper_id,
                "section": primary_section,
                "content": f"Evidence for {primary_section}.",
                "score": 0.99,
            },
            *(
                [
                    {
                        "chunk_id": f"{sample.sample_id}-{secondary_section.lower()}-gold-2",
                        "paper_id": sample.paper_id,
                        "section": secondary_section,
                        "content": f"Evidence for {secondary_section}.",
                        "score": 0.93,
                    }
                ]
                if secondary_section
                else [
                    {
                        "chunk_id": f"{sample.sample_id}-hybrid-rerank-support-2",
                        "paper_id": sample.paper_id,
                        "section": primary_section,
                        "content": f"Additional evidence for {primary_section}.",
                        "score": 0.9,
                    }
                ]
            ),
            {
                "chunk_id": f"{sample.sample_id}-hybrid-distractor-1",
                "paper_id": sample.paper_id,
                "section": "Background",
                "content": "Keyword overlap but incomplete support.",
                "score": 0.61,
            },
        ][:top_k],
    }


def test_compute_retrieval_metrics_handles_hit_recall_and_mrr():
    from app.evaluation.metrics import compute_retrieval_metrics

    relevant = {"chunk-2", "chunk-4"}
    retrieved = ["chunk-1", "chunk-2", "chunk-3"]

    metrics = compute_retrieval_metrics(
        retrieved_chunk_ids=retrieved, relevant_chunk_ids=relevant, top_k=3
    )

    assert metrics["hit_at_k"] is True
    assert metrics["recall_at_k"] == 0.5
    assert metrics["mrr"] == 0.5
    assert metrics["first_relevant_rank"] == 2


@pytest.mark.parametrize(
    ("retrieved", "relevant", "expected_hit", "expected_recall", "expected_mrr"),
    [
        ([], {"chunk-1"}, False, 0.0, 0.0),
        (["chunk-1", "chunk-2"], set(), False, 0.0, 0.0),
        (["chunk-3", "chunk-1"], {"chunk-1"}, True, 1.0, 0.5),
    ],
)
def test_compute_retrieval_metrics_edge_cases(
    retrieved, relevant, expected_hit, expected_recall, expected_mrr
):
    from app.evaluation.metrics import compute_retrieval_metrics

    metrics = compute_retrieval_metrics(
        retrieved_chunk_ids=retrieved, relevant_chunk_ids=relevant, top_k=5
    )

    assert metrics["hit_at_k"] is expected_hit
    assert metrics["recall_at_k"] == expected_recall
    assert metrics["mrr"] == expected_mrr


def test_evaluate_retrieval_sample_marks_relevant_matches_and_aggregates():
    from app.evaluation.metrics import evaluate_retrieval_sample

    sample = QAEvalSample(
        sample_id="qa-1",
        question="What does the paper mainly propose?",
        expected_answer="An answer",
        paper_id="paper-1",
        paper_title="Paper 1",
        supporting_sections=["Abstract", "Method"],
    )
    retrieved_chunks = [
        {"chunk_id": "c1", "paper_id": "paper-2", "section": "Abstract", "score": 0.99},
        {"chunk_id": "c2", "paper_id": "paper-1", "section": "Method", "score": 0.88},
        {"chunk_id": "c3", "paper_id": "paper-1", "section": "Results", "score": 0.77},
    ]

    result = evaluate_retrieval_sample(
        sample=sample, retrieved_chunks=retrieved_chunks, top_k=3
    )

    assert result.sample_id == "qa-1"
    assert result.hit_at_k is True
    assert result.recall_at_k == 0.5
    assert result.mrr == 0.5
    assert [match.rank for match in result.retrieved_chunks] == [1, 2, 3]
    assert [match.is_relevant for match in result.retrieved_chunks] == [
        False,
        True,
        False,
    ]


def test_summarize_retrieval_results_produces_reportable_aggregate_metrics():
    from app.evaluation.metrics import summarize_retrieval_results
    from app.evaluation.schemas import RetrievalEvalResult, RetrievalMatch

    results = [
        RetrievalEvalResult(
            sample_id="qa-1",
            query="q1",
            top_k=3,
            hit_at_k=True,
            recall_at_k=1.0,
            mrr=1.0,
            retrieved_chunks=[
                RetrievalMatch(
                    chunk_id="c1",
                    paper_id="paper-1",
                    section="Abstract",
                    score=0.9,
                    rank=1,
                    is_relevant=True,
                )
            ],
        ),
        RetrievalEvalResult(
            sample_id="qa-2",
            query="q2",
            top_k=3,
            hit_at_k=False,
            recall_at_k=0.0,
            mrr=0.0,
            retrieved_chunks=[],
        ),
    ]

    summary = summarize_retrieval_results(results, top_k=3)

    assert summary["sample_count"] == 2
    assert summary["top_k"] == 3
    assert summary["hit_rate"] == 0.5
    assert summary["mean_recall"] == 0.5
    assert summary["mrr"] == 0.5
    assert summary["hits"] == 1
    assert summary["misses"] == 1


def test_build_retrieval_variant_results_summarizes_multiple_pipelines():
    from app.evaluation.metrics import build_retrieval_variant_results, load_qa_samples

    samples = load_qa_samples(str(QA_DATASET))[:2]
    retrieved_by_strategy = {
        sample.sample_id: _build_fake_vector_store_results(sample, top_k=3)
        for sample in samples
    }

    payload = build_retrieval_variant_results(
        samples=samples, retrieved_by_strategy=retrieved_by_strategy, top_k=3
    )

    assert payload["summary"]["strategy_count"] == 4
    assert payload["summary"]["best_strategy"] == "dense_rerank"
    assert payload["summary"]["improvements"]["dense_rerank"]["mrr_delta_vs_dense"] > 0
    assert (
        payload["summary"]["improvements"]["hybrid_rerank"]["hit_rate_delta_vs_dense"]
        >= 0
    )
    assert payload["strategy_summaries"]["dense"]["sample_count"] == len(samples)
    assert (
        payload["strategy_summaries"]["dense_rerank"]["mrr"]
        > payload["strategy_summaries"]["dense"]["mrr"]
    )
    assert len(payload["results_by_strategy"]["hybrid"]) == len(samples)


def test_retrieval_script_supports_comparison_mode(tmp_path: Path):
    report_path = tmp_path / "retrieval_compare_report.json"

    result = subprocess.run(
        [
            PYTHON_EXECUTABLE,
            str(SCRIPT_PATH),
            "--dataset",
            str(QA_DATASET),
            "--top-k",
            "3",
            "--mode",
            "compare",
            "--output",
            str(report_path),
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(report_path.read_text(encoding="utf-8"))
    assert payload["summary"]["strategy_count"] == 4
    assert set(payload["strategy_summaries"].keys()) == {
        "dense",
        "dense_rerank",
        "hybrid",
        "hybrid_rerank",
    }
    assert payload["summary"]["best_strategy"] in payload["strategy_summaries"]
    assert payload["summary"]["improvements"]["dense_rerank"]["mrr_delta_vs_dense"] >= 0


def test_evaluate_retrieval_script_emits_json_report(tmp_path: Path):
    report_path = tmp_path / "retrieval_eval_report.json"

    result = subprocess.run(
        [
            PYTHON_EXECUTABLE,
            str(SCRIPT_PATH),
            "--dataset",
            str(QA_DATASET),
            "--top-k",
            "3",
            "--output",
            str(report_path),
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert report_path.exists(), "Retrieval evaluation report was not generated"

    payload = json.loads(report_path.read_text(encoding="utf-8"))
    assert payload["summary"]["sample_count"] >= 1
    assert payload["summary"]["top_k"] == 3
    assert set(payload["summary"].keys()) >= {"hit_rate", "mean_recall", "mrr"}
    assert payload["results"], "Expected per-sample retrieval results"
    first_result = payload["results"][0]
    assert set(first_result.keys()) >= {
        "sample_id",
        "query",
        "top_k",
        "hit_at_k",
        "recall_at_k",
        "mrr",
        "retrieved_chunks",
    }
