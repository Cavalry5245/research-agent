"""analyze_comparison — analyze multi-paper comparison evaluation reports and live events."""

from __future__ import annotations

import argparse
import json
import statistics
from collections import Counter
from pathlib import Path
from typing import Any


def load_comparison_report(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def aspect_coverage(results: list[dict[str, Any]]) -> dict[str, float]:
    aspect_counter: Counter[str] = Counter()
    total = len(results) or 1
    for r in results:
        for aspect in r.get("expected_aspects", []) or []:
            if aspect in r.get("covered_aspects", []) or aspect in r.get(
                "aspects_covered", []
            ):
                aspect_counter[aspect] += 1
    return {aspect: count / total for aspect, count in aspect_counter.items()}


def quality_score_distribution(results: list[dict[str, Any]]) -> dict[str, Any]:
    metric_buckets: dict[str, list[float]] = {}
    metric_names = [
        "completeness",
        "evidence_completeness",
        "evidence_quality",
        "section_alignment",
        "paper_balance",
    ]
    for r in results:
        for metric in metric_names:
            value = r.get(metric)
            if value is not None:
                metric_buckets.setdefault(metric, []).append(float(value))
    out: dict[str, Any] = {}
    for metric, values in metric_buckets.items():
        if not values:
            continue
        out[metric] = {
            "count": len(values),
            "mean": statistics.mean(values),
            "min": min(values),
            "max": max(values),
            "stdev": statistics.stdev(values) if len(values) > 1 else 0.0,
        }
    return out


def comparison_event_time_distribution(events_path: Path) -> dict[str, Any]:
    if not events_path.exists():
        return {"count": 0}
    points: list[tuple[int, float]] = []
    for line in events_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            rec = json.loads(line)
        except json.JSONDecodeError:
            continue
        if rec.get("event_type") != "comparison":
            continue
        payload = rec.get("payload", {})
        paper_count = payload.get("paper_count")
        generation_time = payload.get("generation_time")
        if paper_count is None or generation_time is None:
            continue
        points.append((int(paper_count), float(generation_time)))

    by_count: dict[int, list[float]] = {}
    for count, t in points:
        by_count.setdefault(count, []).append(t)

    return {
        "count": len(points),
        "mean_time_by_paper_count": {
            k: statistics.mean(v) for k, v in by_count.items()
        },
        "all_points": points,
    }


def analyze_comparison_report(
    report_path: Path, events_path: Path | None = None
) -> dict[str, Any]:
    report = load_comparison_report(report_path)
    results = report.get("results", [])
    payload = {
        "report_path": str(report_path),
        "summary": report.get("summary", {}),
        "aspect_coverage": aspect_coverage(results),
        "quality_score_distribution": quality_score_distribution(results),
        "sample_count": len(results),
    }
    if events_path:
        payload["live_event_time_distribution"] = comparison_event_time_distribution(
            events_path
        )
    return payload


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Analyze comparison evaluation report and live events."
    )
    parser.add_argument(
        "--input",
        type=Path,
        default=Path("app/evaluation/reports/comparison_eval_seed_report.json"),
    )
    parser.add_argument(
        "--events", type=Path, default=Path("app/storage/analytics/events.jsonl")
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("app/analytics/reports/comparison_analysis.json"),
    )
    args = parser.parse_args()

    payload = analyze_comparison_report(args.input, events_path=args.events)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"Generated comparison analysis: {args.output}")
    print(
        json.dumps(
            {
                "summary": payload["summary"],
                "quality_score_distribution": payload["quality_score_distribution"],
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
