"""Unit tests for failure_detector and failure_analyzer."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.analytics.data_collector import AnalyticsCollector
from app.analytics.failure_analyzer import (
    analyze_comparison_failures,
    analyze_qa_failures,
    analyze_retrieval_failures,
    build_failure_report,
    load_failures,
    render_markdown_report,
    top_failure_modes,
)
from app.analytics.failure_detector import FailureCase, FailureDetector


@pytest.fixture
def detector() -> FailureDetector:
    return FailureDetector(
        retrieval_score_threshold=0.5,
        qa_pass_score_threshold=0.5,
        comparison_completeness_threshold=0.7,
    )


# ----- FailureDetector -----


def test_detect_retrieval_empty_results(detector: FailureDetector):
    case = detector.detect_retrieval_failure("q", [], sample_id="s1")
    assert case is not None
    assert case.failure_type == "retrieval_no_results"
    assert case.sample_id == "s1"


def test_detect_retrieval_low_score(detector: FailureDetector):
    case = detector.detect_retrieval_failure(
        "q", [{"score": 0.1, "is_relevant": False}], sample_id="s2"
    )
    assert case is not None
    assert case.failure_type == "retrieval_low_score"


def test_detect_retrieval_irrelevant(detector: FailureDetector):
    case = detector.detect_retrieval_failure(
        "q", [{"score": 0.9, "is_relevant": False}], sample_id="s3"
    )
    assert case is not None
    assert case.failure_type == "retrieval_irrelevant"


def test_detect_retrieval_success(detector: FailureDetector):
    case = detector.detect_retrieval_failure("q", [{"score": 0.9, "is_relevant": True}])
    assert case is None


def test_detect_qa_empty_answer(detector: FailureDetector):
    case = detector.detect_qa_failure("q?", "", sample_id="qa1")
    assert case is not None
    assert case.failure_type == "qa_empty_answer"


def test_detect_qa_low_score(detector: FailureDetector):
    case = detector.detect_qa_failure(
        "q?", "ans", answer_evaluation={"score": 0.2, "passed": False}, sample_id="qa2"
    )
    assert case is not None
    assert case.failure_type == "qa_low_score"


def test_detect_qa_bad_citation(detector: FailureDetector):
    case = detector.detect_qa_failure(
        "q?",
        "ans",
        answer_evaluation={"score": 0.9, "passed": True},
        citation_evaluation={"score": 0.1, "passed": False},
        sample_id="qa3",
    )
    assert case is not None
    assert case.failure_type == "qa_bad_citation"


def test_detect_qa_success(detector: FailureDetector):
    case = detector.detect_qa_failure(
        "q?",
        "answer",
        answer_evaluation={"score": 0.95, "passed": True},
        citation_evaluation={"score": 0.95, "passed": True},
    )
    assert case is None


def test_detect_comparison_low_completeness(detector: FailureDetector):
    case = detector.detect_comparison_failure(
        {"completeness": 0.3, "evidence_quality": 0.8}
    )
    assert case is not None
    assert case.failure_type == "comparison_incomplete"


def test_detect_comparison_weak_evidence(detector: FailureDetector):
    case = detector.detect_comparison_failure(
        {"completeness": 0.9, "evidence_quality": 0.3}
    )
    assert case is not None
    assert case.failure_type == "comparison_weak_evidence"


def test_detector_record_emits_to_collector(detector: FailureDetector, tmp_path: Path):
    collector = AnalyticsCollector(
        events_path=tmp_path / "ev.jsonl", failures_path=tmp_path / "fail.jsonl"
    )
    case = detector.detect_retrieval_failure("q", [], sample_id="rec1")
    detector.record(case, collector=collector)
    failures = collector.read_failures()
    assert len(failures) == 1
    assert failures[0].payload["failure_type"] == "retrieval_no_results"


def test_detector_record_handles_none_gracefully(
    detector: FailureDetector, tmp_path: Path
):
    collector = AnalyticsCollector(
        events_path=tmp_path / "ev.jsonl", failures_path=tmp_path / "fail.jsonl"
    )
    detector.record(None, collector=collector)
    assert len(collector.read_failures()) == 0


# ----- FailureAnalyzer -----


def _write_failures(tmp_path: Path, cases: list[dict]) -> Path:
    path = tmp_path / "failures.jsonl"
    path.write_text("\n".join(json.dumps(c) for c in cases) + "\n", encoding="utf-8")
    return path


def test_load_failures(tmp_path: Path):
    path = _write_failures(
        tmp_path,
        [
            {
                "event_type": "failure",
                "timestamp": "t",
                "payload": {"failure_type": "retrieval_low_score"},
            }
        ],
    )
    cases = load_failures(path)
    assert len(cases) == 1


def test_top_failure_modes_counts_by_type(tmp_path: Path):
    cases = [
        {"payload": {"failure_type": "qa_low_score"}},
        {"payload": {"failure_type": "qa_low_score"}},
        {"payload": {"failure_type": "retrieval_no_results"}},
    ]
    top = top_failure_modes(cases, n=2)
    assert top[0] == ("qa_low_score", 2)


def test_analyze_retrieval_failures_groups_by_paper():
    cases = [
        {
            "payload": {
                "failure_type": "retrieval_low_score",
                "context": {"paper_id": "p1", "query": "alpha beta gamma"},
            }
        },
        {
            "payload": {
                "failure_type": "retrieval_no_results",
                "context": {"paper_id": "p2", "query": "delta epsilon"},
            }
        },
    ]
    report = analyze_retrieval_failures(cases)
    assert report["total"] == 2
    assert report["by_paper"] == {"p1": 1, "p2": 1}
    assert report["sub_type_counts"] == {
        "retrieval_low_score": 1,
        "retrieval_no_results": 1,
    }


def test_analyze_qa_failures_counts_empty_and_long_answers():
    cases = [
        {
            "payload": {
                "failure_type": "qa_empty_answer",
                "context": {"sample_id": "s1", "answer": ""},
            }
        },
        {
            "payload": {
                "failure_type": "qa_low_score",
                "context": {"sample_id": "s2", "answer": "x" * 900},
            }
        },
    ]
    report = analyze_qa_failures(cases)
    assert report["total"] == 2
    assert report["empty_answer_count"] == 1
    assert report["long_answer_count"] == 1


def test_analyze_comparison_failures_average_completeness():
    cases = [
        {
            "payload": {
                "failure_type": "comparison_incomplete",
                "context": {"completeness": 0.3},
            }
        },
        {
            "payload": {
                "failure_type": "comparison_incomplete",
                "context": {"completeness": 0.5},
            }
        },
    ]
    report = analyze_comparison_failures(cases)
    assert report["total"] == 2
    assert report["mean_completeness_in_failures"] == pytest.approx(0.4)


def test_build_failure_report_end_to_end(tmp_path: Path):
    path = _write_failures(
        tmp_path,
        [
            {
                "payload": {
                    "failure_type": "retrieval_low_score",
                    "context": {"paper_id": "p1", "query": "alpha"},
                }
            },
            {
                "payload": {
                    "failure_type": "qa_low_score",
                    "context": {"sample_id": "s1", "answer": "x"},
                }
            },
            {
                "payload": {
                    "failure_type": "comparison_incomplete",
                    "context": {"completeness": 0.4},
                }
            },
        ],
    )
    report = build_failure_report(path)
    assert report["total_failures"] == 3
    assert report["retrieval"]["total"] == 1
    assert report["qa"]["total"] == 1
    assert report["comparison"]["total"] == 1


def test_render_markdown_report_includes_sections():
    report = {
        "total_failures": 0,
        "top_failure_modes": [],
        "retrieval": {"total": 0, "sub_type_counts": {}},
        "qa": {
            "total": 0,
            "sub_type_counts": {},
            "empty_answer_count": 0,
            "long_answer_count": 0,
        },
        "comparison": {"total": 0, "sub_type_counts": {}},
    }
    md = render_markdown_report(report)
    assert "Top Failure Modes" in md
    assert "Retrieval Failures" in md
    assert "QA Failures" in md
    assert "Comparison Failures" in md
    assert "Optimization Suggestions" in md


def test_render_markdown_report_emits_suggestions():
    report = build_failure_report_from_inline(
        [
            {"payload": {"failure_type": "retrieval_no_results", "context": {}}},
            {"payload": {"failure_type": "qa_empty_answer", "context": {}}},
        ]
    )
    md = render_markdown_report(report)
    assert "Optimization Suggestions" in md
    # Specific suggestion text should appear
    assert "recall" in md.lower() or "audit" in md.lower()


def build_failure_report_from_inline(cases: list[dict]) -> dict:
    return {
        "total_failures": len(cases),
        "top_failure_modes": top_failure_modes(cases),
        "retrieval": analyze_retrieval_failures(cases),
        "qa": analyze_qa_failures(cases),
        "comparison": analyze_comparison_failures(cases),
    }
