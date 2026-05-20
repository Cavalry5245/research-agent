"""analyze_qa — analyze QA evaluation reports and live QA event logs."""

from __future__ import annotations

import argparse
import json
import statistics
from collections import Counter
from pathlib import Path
from typing import Any


def load_qa_report(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def answer_length_distribution(results: list[dict[str, Any]]) -> dict[str, float]:
    lengths = [len(r.get("predicted_answer", "") or "") for r in results]
    if not lengths:
        return {"count": 0, "mean": 0.0, "median": 0.0, "p95": 0.0}
    lengths_sorted = sorted(lengths)
    p95_idx = max(0, int(len(lengths_sorted) * 0.95) - 1)
    return {
        "count": len(lengths),
        "mean": statistics.mean(lengths),
        "median": statistics.median(lengths),
        "p95": lengths_sorted[p95_idx],
        "min": min(lengths),
        "max": max(lengths),
    }


def citation_accuracy(results: list[dict[str, Any]]) -> dict[str, Any]:
    citation_passes = sum(1 for r in results if r.get("citation_evaluation", {}).get("passed"))
    answer_passes = sum(1 for r in results if r.get("answer_evaluation", {}).get("passed"))
    total = len(results) or 1
    citation_scores = [r.get("citation_evaluation", {}).get("score", 0.0) for r in results]
    answer_scores = [r.get("answer_evaluation", {}).get("score", 0.0) for r in results]
    return {
        "sample_count": total,
        "answer_pass_rate": answer_passes / total,
        "citation_pass_rate": citation_passes / total,
        "mean_answer_score": statistics.mean(answer_scores) if answer_scores else 0.0,
        "mean_citation_score": statistics.mean(citation_scores) if citation_scores else 0.0,
        "answer_score_std": statistics.stdev(answer_scores) if len(answer_scores) > 1 else 0.0,
    }


def top_questions(results: list[dict[str, Any]], n: int = 10) -> list[tuple[str, int]]:
    """Top-N most common question stems (first 60 chars)."""
    counter = Counter()
    for r in results:
        question = (r.get("question") or "")[:60]
        counter[question] += 1
    return counter.most_common(n)


def qa_event_time_breakdown(events_path: Path) -> dict[str, Any]:
    if not events_path.exists():
        return {"count": 0}
    retrieval_times: list[float] = []
    llm_times: list[float] = []
    total_times: list[float] = []
    for line in events_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            rec = json.loads(line)
        except json.JSONDecodeError:
            continue
        if rec.get("event_type") != "qa":
            continue
        payload = rec.get("payload", {})
        if payload.get("retrieval_time") is not None:
            retrieval_times.append(float(payload["retrieval_time"]))
        if payload.get("llm_time") is not None:
            llm_times.append(float(payload["llm_time"]))
        if payload.get("total_time") is not None:
            total_times.append(float(payload["total_time"]))

    def _stats(xs: list[float]) -> dict[str, float]:
        if not xs:
            return {"count": 0, "mean": 0.0, "p95": 0.0}
        xs_sorted = sorted(xs)
        p95_idx = max(0, int(len(xs_sorted) * 0.95) - 1)
        return {
            "count": len(xs_sorted),
            "mean": statistics.mean(xs_sorted),
            "p95": xs_sorted[p95_idx],
            "median": statistics.median(xs_sorted),
        }

    return {
        "retrieval_time": _stats(retrieval_times),
        "llm_time": _stats(llm_times),
        "total_time": _stats(total_times),
    }


def analyze_qa_report(report_path: Path, events_path: Path | None = None) -> dict[str, Any]:
    report = load_qa_report(report_path)
    results = report.get("results", [])
    payload = {
        "report_path": str(report_path),
        "summary": report.get("summary", {}),
        "answer_length_distribution": answer_length_distribution(results),
        "citation_accuracy": citation_accuracy(results),
        "top_questions": top_questions(results),
    }
    if events_path:
        payload["live_event_time_breakdown"] = qa_event_time_breakdown(events_path)
    return payload


def main() -> None:
    parser = argparse.ArgumentParser(description="Analyze QA evaluation report and live events.")
    parser.add_argument("--input", type=Path, default=Path("app/evaluation/reports/qa_eval_seed_report.json"))
    parser.add_argument("--events", type=Path, default=Path("app/storage/analytics/events.jsonl"))
    parser.add_argument("--output", type=Path, default=Path("app/analytics/reports/qa_analysis.json"))
    args = parser.parse_args()

    payload = analyze_qa_report(args.input, events_path=args.events)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Generated QA analysis: {args.output}")
    print(json.dumps({"summary": payload["summary"], "answer_length_distribution": payload["answer_length_distribution"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
