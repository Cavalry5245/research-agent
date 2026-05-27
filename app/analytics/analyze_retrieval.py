"""analyze_retrieval — compute retrieval analytics from evaluation reports / live event logs.

Works directly off the dict-shaped JSON written by evaluate_retrieval.py
(no need to reconstruct Pydantic models — the script may extend the schema later).
"""

from __future__ import annotations

import argparse
import json
import statistics
from collections import defaultdict
from pathlib import Path
from typing import Any


def load_retrieval_report(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def hit_at_k_curve(
    results: list[dict[str, Any]], ks: list[int] | None = None
) -> dict[int, float]:
    """Compute Hit@K for each K in `ks` over a list of retrieval result dicts."""
    if ks is None:
        ks = [1, 3, 5, 10]
    total = len(results) or 1
    curve: dict[int, float] = {}
    for k in ks:
        hits = 0
        for r in results:
            chunks = r.get("retrieved_chunks") or []
            top_k_chunks = chunks[:k]
            if any(c.get("is_relevant") for c in top_k_chunks):
                hits += 1
        curve[k] = hits / total
    return curve


def cluster_failures(results: list[dict[str, Any]]) -> dict[str, dict[str, list[str]]]:
    """Group failed sample_ids by paper_id and by expected section heading."""
    by_paper: dict[str, list[str]] = defaultdict(list)
    by_section: dict[str, list[str]] = defaultdict(list)
    for r in results:
        passed = bool(r.get("hit_at_k"))
        if passed:
            continue
        sample_id = r.get("sample_id", "?")
        # paper_id may live on chunks; pick first known
        chunks = r.get("retrieved_chunks") or []
        paper_id = chunks[0].get("paper_id") if chunks else r.get("paper_id")
        by_paper[paper_id or "unknown"].append(sample_id)
        for c in chunks:
            sect = c.get("section") or "__unknown__"
            by_section[sect].append(sample_id)
    return {"by_paper": dict(by_paper), "by_section": dict(by_section)}


def time_distribution(timings: list[float]) -> dict[str, float]:
    if not timings:
        return {"count": 0, "mean": 0.0, "median": 0.0, "p95": 0.0, "stdev": 0.0}
    timings = sorted(timings)
    p95_idx = max(0, int(len(timings) * 0.95) - 1)
    stdev = statistics.stdev(timings) if len(timings) > 1 else 0.0
    return {
        "count": len(timings),
        "mean": statistics.mean(timings),
        "median": statistics.median(timings),
        "p95": timings[p95_idx],
        "stdev": stdev,
    }


def summarize_aggregate(results: list[dict[str, Any]]) -> dict[str, float]:
    if not results:
        return {
            "sample_count": 0,
            "hit_rate": 0.0,
            "mean_recall_at_k": 0.0,
            "mean_mrr": 0.0,
        }
    return {
        "sample_count": len(results),
        "hit_rate": sum(1 for r in results if r.get("hit_at_k")) / len(results),
        "mean_recall_at_k": statistics.mean(
            [float(r.get("recall_at_k", 0.0)) for r in results]
        ),
        "mean_mrr": statistics.mean([float(r.get("mrr", 0.0)) for r in results]),
    }


def analyze_retrieval_report(path: Path, ks: list[int] | None = None) -> dict[str, Any]:
    report = load_retrieval_report(path)
    results = report.get("results", [])
    return {
        "report_path": str(path),
        "sample_count": len(results),
        "hit_at_k_curve": hit_at_k_curve(results, ks=ks),
        "failure_clusters": cluster_failures(results),
        "summary": summarize_aggregate(results),
    }


def analyze_qa_event_retrieval_times(events_path: Path) -> dict[str, float]:
    if not events_path.exists():
        return {"count": 0}
    retrieval_times: list[float] = []
    for line in events_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            continue
        if record.get("event_type") != "qa":
            continue
        rt = record.get("payload", {}).get("retrieval_time")
        if rt is not None:
            retrieval_times.append(float(rt))
    return time_distribution(retrieval_times)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Analyze retrieval evaluation reports and event logs."
    )
    parser.add_argument(
        "--input",
        type=Path,
        default=Path("app/evaluation/reports/retrieval_eval_seed_report.json"),
    )
    parser.add_argument(
        "--events", type=Path, default=Path("app/storage/analytics/events.jsonl")
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("app/analytics/reports/retrieval_analysis.json"),
    )
    args = parser.parse_args()

    report = analyze_retrieval_report(args.input)
    report["live_retrieval_time"] = analyze_qa_event_retrieval_times(args.events)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"Generated retrieval analysis: {args.output}")
    print(
        json.dumps(
            {"summary": report["summary"], "hit_at_k_curve": report["hit_at_k_curve"]},
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
