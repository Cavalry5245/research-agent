import json
import os
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.evaluation.reporting import (
    build_baseline_report_markdown,
    build_baseline_report_payload,
    build_retrieval_upgrade_report_markdown,
    build_retrieval_upgrade_report_payload,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
RETRIEVAL_REPORT = (
    REPO_ROOT / "app" / "evaluation" / "reports" / "retrieval_eval_seed_report.json"
)
QA_DATASET = REPO_ROOT / "app" / "evaluation" / "datasets" / "qa_eval_seed.jsonl"
REPORTING_SCRIPT = REPO_ROOT / "app" / "evaluation" / "reporting.py"
PYTHON_EXECUTABLE = sys.executable


def test_build_baseline_report_payload_collects_required_sections():
    payload = build_baseline_report_payload(
        retrieval_report_path=RETRIEVAL_REPORT,
        dataset_path=QA_DATASET,
        top_k=3,
        environment_summary="WSL + conda",
        validation_summary="Offline deterministic retrieval baseline; real retrieval chain not yet wired.",
    )

    assert payload["dataset_scale"]["qa_sample_count"] >= 1
    assert payload["retrieval_configuration"]["top_k"] == 3
    assert set(payload["metrics"].keys()) >= {"hit_at_k", "recall_at_k", "mrr"}
    assert payload["failed_case_samples"]
    assert any(case["failure_reason"] for case in payload["failed_case_samples"])
    assert payload["next_step_recommendations"]
    assert payload["environment_notes"]["environment"] == "WSL + conda"
    assert "Offline" in payload["environment_notes"]["validation"]


def test_build_baseline_report_markdown_renders_required_content():
    payload = build_baseline_report_payload(
        retrieval_report_path=RETRIEVAL_REPORT,
        dataset_path=QA_DATASET,
        top_k=3,
        environment_summary="WSL + conda",
        validation_summary="Offline deterministic retrieval baseline; real retrieval chain not yet wired.",
    )

    markdown = build_baseline_report_markdown(payload)

    assert "# Retrieval Baseline Report" in markdown
    assert "## Dataset Scale" in markdown
    assert "## Retrieval Configuration" in markdown
    assert "## Metrics" in markdown
    assert "Hit@3" in markdown
    assert "Recall@3" in markdown
    assert "MRR" in markdown
    assert "## Failed Case Samples" in markdown
    assert "## Next-Step Recommendations" in markdown
    assert "## Environment and Validation Notes" in markdown


def test_reporting_script_generates_markdown_report(tmp_path: Path):
    output_path = tmp_path / "baseline_report.md"

    result = subprocess.run(
        [
            PYTHON_EXECUTABLE,
            str(REPORTING_SCRIPT),
            "--retrieval-report",
            str(RETRIEVAL_REPORT),
            "--dataset",
            str(QA_DATASET),
            "--top-k",
            "3",
            "--output",
            str(output_path),
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert output_path.exists(), "Baseline markdown report was not generated"

    content = output_path.read_text(encoding="utf-8")
    assert "# Retrieval Baseline Report" in content
    assert "Hit@3" in content
    assert "Failed Case Samples" in content


def test_build_retrieval_upgrade_report_payload_summarizes_strategy_deltas():
    comparison_report = {
        "summary": {
            "strategy_count": 4,
            "best_strategy": "dense_rerank",
            "baseline_strategy": "dense",
            "improvements": {
                "dense_rerank": {
                    "hit_rate_delta_vs_dense": 0.0,
                    "mean_recall_delta_vs_dense": 0.5,
                    "mrr_delta_vs_dense": 0.5,
                },
                "hybrid": {
                    "hit_rate_delta_vs_dense": 0.0,
                    "mean_recall_delta_vs_dense": 0.0,
                    "mrr_delta_vs_dense": 0.25,
                },
                "hybrid_rerank": {
                    "hit_rate_delta_vs_dense": 0.0,
                    "mean_recall_delta_vs_dense": 0.5,
                    "mrr_delta_vs_dense": 0.5,
                },
            },
        },
        "strategy_summaries": {
            "dense": {
                "sample_count": 2,
                "hit_rate": 1.0,
                "mean_recall": 0.5,
                "mrr": 0.5,
                "hits": 2,
                "misses": 0,
            },
            "dense_rerank": {
                "sample_count": 2,
                "hit_rate": 1.0,
                "mean_recall": 1.0,
                "mrr": 1.0,
                "hits": 2,
                "misses": 0,
            },
            "hybrid": {
                "sample_count": 2,
                "hit_rate": 1.0,
                "mean_recall": 0.5,
                "mrr": 0.75,
                "hits": 2,
                "misses": 0,
            },
            "hybrid_rerank": {
                "sample_count": 2,
                "hit_rate": 1.0,
                "mean_recall": 1.0,
                "mrr": 1.0,
                "hits": 2,
                "misses": 0,
            },
        },
        "results_by_strategy": {
            "dense": [
                {
                    "sample_id": "qa-1",
                    "query": "q1",
                    "top_k": 3,
                    "hit_at_k": True,
                    "recall_at_k": 0.5,
                    "mrr": 0.5,
                    "retrieved_chunks": [
                        {
                            "chunk_id": "dense-d1",
                            "paper_id": "paper-1",
                            "section": "Conclusion",
                            "score": 0.96,
                            "rank": 1,
                            "is_relevant": False,
                        },
                        {
                            "chunk_id": "dense-g1",
                            "paper_id": "paper-1",
                            "section": "Abstract",
                            "score": 0.81,
                            "rank": 2,
                            "is_relevant": True,
                        },
                    ],
                }
            ],
            "dense_rerank": [
                {
                    "sample_id": "qa-1",
                    "query": "q1",
                    "top_k": 3,
                    "hit_at_k": True,
                    "recall_at_k": 1.0,
                    "mrr": 1.0,
                    "retrieved_chunks": [
                        {
                            "chunk_id": "dense-r1",
                            "paper_id": "paper-1",
                            "section": "Abstract",
                            "score": 0.98,
                            "rank": 1,
                            "is_relevant": True,
                        },
                    ],
                }
            ],
            "hybrid": [],
            "hybrid_rerank": [],
        },
    }

    payload = build_retrieval_upgrade_report_payload(comparison_report)

    assert payload["overview"]["best_strategy"] == "dense_rerank"
    assert payload["strategies"]["dense_rerank"]["mrr"] == 1.0
    assert payload["improvements"]["dense_rerank"]["mrr_delta_vs_dense"] == 0.5
    assert payload["failure_case_samples"]["dense"]
    assert payload["recommendations"]


def test_build_retrieval_upgrade_report_markdown_renders_required_sections():
    comparison_report = {
        "summary": {
            "strategy_count": 4,
            "best_strategy": "dense_rerank",
            "baseline_strategy": "dense",
            "improvements": {
                "dense_rerank": {
                    "hit_rate_delta_vs_dense": 0.0,
                    "mean_recall_delta_vs_dense": 0.5,
                    "mrr_delta_vs_dense": 0.5,
                }
            },
        },
        "strategy_summaries": {
            "dense": {
                "sample_count": 2,
                "hit_rate": 1.0,
                "mean_recall": 0.5,
                "mrr": 0.5,
                "hits": 2,
                "misses": 0,
            },
            "dense_rerank": {
                "sample_count": 2,
                "hit_rate": 1.0,
                "mean_recall": 1.0,
                "mrr": 1.0,
                "hits": 2,
                "misses": 0,
            },
        },
        "results_by_strategy": {"dense": [], "dense_rerank": []},
    }

    payload = build_retrieval_upgrade_report_payload(comparison_report)
    markdown = build_retrieval_upgrade_report_markdown(payload)

    assert "# Retrieval Upgrade Report" in markdown
    assert "## Overview" in markdown
    assert "## Strategy Metrics" in markdown
    assert "dense_rerank" in markdown
    assert "## Improvements vs Dense Baseline" in markdown
    assert "## Failure Case Samples" in markdown
    assert "## Next-Step Recommendations" in markdown
