"""Unit tests for app/analytics/."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.analytics.data_collector import AnalyticsCollector, AnalyticsEvent, reset_collector_singleton
from app.analytics import analyze_comparison, analyze_qa, analyze_retrieval, visualizer


# ---------------- AnalyticsCollector ----------------


@pytest.fixture
def collector(tmp_path: Path) -> AnalyticsCollector:
    return AnalyticsCollector(events_path=tmp_path / "events.jsonl", failures_path=tmp_path / "failures.jsonl")


def test_log_qa_request_persists_event(collector: AnalyticsCollector):
    event = collector.log_qa_request(
        paper_id="p1", question="q?", answer="ans", retrieval_time=0.1, llm_time=0.4, sources_count=2, top_k=5
    )
    assert isinstance(event, AnalyticsEvent)
    assert event.event_type == "qa"
    events = collector.read_events("qa")
    assert len(events) == 1
    assert events[0].payload["retrieval_time"] == 0.1
    assert events[0].payload["sources_count"] == 2


def test_log_comparison_and_indexing_and_note(collector: AnalyticsCollector):
    collector.log_comparison(["p1", "p2"], generation_time=1.2, result_length=500, aspects_count=3)
    collector.log_indexing("p1", chunk_count=8, embedding_time=0.3, parse_time=0.05, persist_time=0.02)
    collector.log_note("p1", llm_time=2.0, content_length=1200)
    events = collector.read_events()
    types = {e.event_type for e in events}
    assert types == {"comparison", "indexing", "note"}


def test_log_failure_writes_to_failures_file(collector: AnalyticsCollector):
    collector.log_failure("retrieval", {"paper_id": "p1", "query": "q"}, reason="low score")
    collector.log_failure("qa", {"paper_id": "p2"}, reason="hallucination")
    assert len(collector.read_failures()) == 2
    assert len(collector.read_failures("retrieval")) == 1


def test_invalid_event_type_raises(collector: AnalyticsCollector):
    with pytest.raises(ValueError):
        collector.log_event("bogus_type", x=1)


def test_singleton_resets(tmp_path: Path, monkeypatch):
    reset_collector_singleton()
    monkeypatch.setenv("ANALYTICS_EVENTS_PATH", str(tmp_path / "ev.jsonl"))
    monkeypatch.setenv("ANALYTICS_FAILURES_PATH", str(tmp_path / "fail.jsonl"))
    from app.analytics import get_collector

    c1 = get_collector()
    c2 = get_collector()
    assert c1 is c2
    reset_collector_singleton()


# ---------------- analyze_retrieval ----------------


def _write_retrieval_report(path: Path, results: list[dict]) -> None:
    path.write_text(json.dumps({"dataset": "x", "summary": {}, "results": results}, ensure_ascii=False), encoding="utf-8")


def test_analyze_retrieval_hit_at_k_curve():
    results = [
        {"sample_id": "1", "hit_at_k": True, "recall_at_k": 1.0, "mrr": 1.0,
         "retrieved_chunks": [{"is_relevant": True, "section": "A", "paper_id": "p1"}]},
        {"sample_id": "2", "hit_at_k": True, "recall_at_k": 0.5, "mrr": 0.5,
         "retrieved_chunks": [{"is_relevant": False}, {"is_relevant": True}]},
        {"sample_id": "3", "hit_at_k": False, "recall_at_k": 0.0, "mrr": 0.0,
         "retrieved_chunks": [{"is_relevant": False, "section": "B", "paper_id": "p2"}]},
    ]
    curve = analyze_retrieval.hit_at_k_curve(results, ks=[1, 2])
    # K=1: sample 1 hits, sample 2 misses (first chunk not relevant), sample 3 misses → 1/3
    assert curve[1] == pytest.approx(1 / 3)
    # K=2: sample 1 hits, sample 2 hits (chunk 2 is relevant), sample 3 misses → 2/3
    assert curve[2] == pytest.approx(2 / 3)


def test_analyze_retrieval_cluster_failures():
    results = [
        {"sample_id": "1", "hit_at_k": True, "retrieved_chunks": []},
        {"sample_id": "2", "hit_at_k": False,
         "retrieved_chunks": [{"paper_id": "p1", "section": "Method"}]},
    ]
    clusters = analyze_retrieval.cluster_failures(results)
    assert clusters["by_paper"] == {"p1": ["2"]}
    assert clusters["by_section"] == {"Method": ["2"]}


def test_analyze_retrieval_full_report(tmp_path: Path):
    report_path = tmp_path / "r.json"
    _write_retrieval_report(report_path, [
        {"sample_id": "1", "hit_at_k": True, "recall_at_k": 1.0, "mrr": 1.0,
         "retrieved_chunks": [{"is_relevant": True}]}
    ])
    out = analyze_retrieval.analyze_retrieval_report(report_path)
    assert out["sample_count"] == 1
    assert out["hit_at_k_curve"][1] == 1.0
    assert out["summary"]["hit_rate"] == 1.0


# ---------------- analyze_qa ----------------


def test_answer_length_distribution_basic():
    results = [{"predicted_answer": "a" * 10}, {"predicted_answer": "a" * 20}]
    dist = analyze_qa.answer_length_distribution(results)
    assert dist["count"] == 2
    assert dist["min"] == 10
    assert dist["max"] == 20


def test_citation_accuracy():
    results = [
        {"answer_evaluation": {"passed": True, "score": 0.9},
         "citation_evaluation": {"passed": True, "score": 1.0}},
        {"answer_evaluation": {"passed": False, "score": 0.3},
         "citation_evaluation": {"passed": False, "score": 0.2}},
    ]
    acc = analyze_qa.citation_accuracy(results)
    assert acc["sample_count"] == 2
    assert acc["answer_pass_rate"] == 0.5
    assert acc["citation_pass_rate"] == 0.5


def test_top_questions_returns_top_n():
    results = [{"question": "What is X?"}] * 3 + [{"question": "What is Y?"}]
    top = analyze_qa.top_questions(results, n=2)
    assert top[0][0].startswith("What is X")
    assert top[0][1] == 3


def test_qa_event_time_breakdown(tmp_path: Path):
    events_path = tmp_path / "events.jsonl"
    events_path.write_text("\n".join([
        json.dumps({"event_type": "qa", "timestamp": "t1",
                    "payload": {"retrieval_time": 0.1, "llm_time": 0.5, "total_time": 0.6}}),
        json.dumps({"event_type": "qa", "timestamp": "t2",
                    "payload": {"retrieval_time": 0.2, "llm_time": 0.3, "total_time": 0.5}}),
        json.dumps({"event_type": "indexing", "timestamp": "t3", "payload": {"total_time": 5.0}}),
    ]) + "\n", encoding="utf-8")
    breakdown = analyze_qa.qa_event_time_breakdown(events_path)
    assert breakdown["retrieval_time"]["count"] == 2
    assert breakdown["llm_time"]["count"] == 2
    assert breakdown["total_time"]["count"] == 2


def test_analyze_qa_report_accepts_llm_summary_format(tmp_path: Path):
    report_path = tmp_path / "llm_report.json"
    report_path.write_text(
        json.dumps(
            {
                "llm_summary": {"sample_count": 1, "evaluation_mode": "llm", "answer_pass_rate": 0.8},
                "results": [
                    {
                        "sample_id": "s1",
                        "question": "Q?",
                        "predicted_answer": "answer",
                        "answer_evaluation": {"score": 0.8, "passed": True},
                        "citation_evaluation": {"score": 0.7, "passed": True},
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    payload = analyze_qa.analyze_qa_report(report_path)
    assert payload["summary"]["evaluation_mode"] == "llm"
    assert payload["summary"]["answer_pass_rate"] == 0.8
    assert payload["answer_length_distribution"]["count"] == 1


# ---------------- analyze_comparison ----------------


def test_quality_score_distribution():
    results = [
        {"completeness": 0.9, "evidence_quality": 0.8},
        {"completeness": 0.7, "evidence_quality": 0.6},
    ]
    dist = analyze_comparison.quality_score_distribution(results)
    assert dist["completeness"]["count"] == 2
    assert dist["completeness"]["mean"] == pytest.approx(0.8)


def test_comparison_event_time_distribution(tmp_path: Path):
    events_path = tmp_path / "events.jsonl"
    events_path.write_text("\n".join([
        json.dumps({"event_type": "comparison", "timestamp": "t",
                    "payload": {"paper_count": 2, "generation_time": 1.0}}),
        json.dumps({"event_type": "comparison", "timestamp": "t",
                    "payload": {"paper_count": 3, "generation_time": 2.5}}),
    ]) + "\n", encoding="utf-8")
    dist = analyze_comparison.comparison_event_time_distribution(events_path)
    assert dist["count"] == 2
    assert dist["mean_time_by_paper_count"][2] == 1.0
    assert dist["mean_time_by_paper_count"][3] == 2.5


# ---------------- visualizer ----------------


def test_plot_hit_at_k_curve_returns_figure():
    fig = visualizer.plot_hit_at_k_curve({1: 0.5, 3: 0.8, 5: 0.9, 10: 0.95})
    assert fig.axes  # has at least one axis


def test_plot_response_time_distribution_with_data():
    fig = visualizer.plot_response_time_distribution([0.1, 0.2, 0.3, 0.4, 0.5])
    assert fig.axes


def test_plot_response_time_distribution_empty():
    fig = visualizer.plot_response_time_distribution([])
    assert fig.axes


def test_plot_failure_case_heatmap():
    fig = visualizer.plot_failure_case_heatmap({"p1": {"Method": 2}, "p2": {"Results": 3}})
    assert fig.axes


def test_plot_metric_comparison_bar():
    fig = visualizer.plot_metric_comparison_bar(
        {"A": {"hit@3": 0.85, "mrr": 0.78}, "B": {"hit@3": 0.91, "mrr": 0.82}}
    )
    assert fig.axes


def test_plot_token_cost_trend():
    events = [
        {"timestamp": "2026-05-20T10:00:00", "payload": {"total_time": 1.2}},
        {"timestamp": "2026-05-20T10:01:00", "payload": {"total_time": 0.8}},
    ]
    fig = visualizer.plot_token_cost_trend(events)
    assert fig.axes


def test_plot_saves_to_disk(tmp_path: Path):
    target = tmp_path / "out.png"
    visualizer.plot_hit_at_k_curve({1: 0.5, 3: 0.8}, output_path=target)
    assert target.exists()
    assert target.stat().st_size > 0
