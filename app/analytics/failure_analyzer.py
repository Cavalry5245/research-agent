"""FailureAnalyzer — cluster and summarize failure cases."""

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


def load_failures(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    cases: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            cases.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return cases


def _payload(case: dict[str, Any]) -> dict[str, Any]:
    return case.get("payload", {}) or {}


def _failure_type(case: dict[str, Any]) -> str:
    return _payload(case).get("failure_type", "unknown")


def analyze_retrieval_failures(cases: list[dict[str, Any]]) -> dict[str, Any]:
    by_paper: dict[str, int] = defaultdict(int)
    by_query_word: Counter[str] = Counter()
    sub_types: Counter[str] = Counter()
    for case in cases:
        if not _failure_type(case).startswith("retrieval"):
            continue
        sub_types[_failure_type(case)] += 1
        ctx = _payload(case).get("context", {})
        paper_id = ctx.get("paper_id") or ctx.get("sample_id", "unknown")
        by_paper[paper_id] += 1
        query = (ctx.get("query") or "").lower()
        for token in [t for t in query.split() if len(t) > 4][:3]:
            by_query_word[token] += 1
    return {
        "total": sum(sub_types.values()),
        "sub_type_counts": dict(sub_types),
        "by_paper": dict(by_paper),
        "top_query_words": by_query_word.most_common(10),
    }


def analyze_qa_failures(cases: list[dict[str, Any]]) -> dict[str, Any]:
    sub_types: Counter[str] = Counter()
    long_answer_failures = 0
    empty_answer_count = 0
    sample_failures: dict[str, int] = defaultdict(int)
    for case in cases:
        ft = _failure_type(case)
        if not ft.startswith("qa"):
            continue
        sub_types[ft] += 1
        ctx = _payload(case).get("context", {})
        sid = ctx.get("sample_id") or "unknown"
        sample_failures[sid] += 1
        answer = ctx.get("answer") or ""
        if not answer.strip():
            empty_answer_count += 1
        elif len(answer) > 800:
            long_answer_failures += 1
    return {
        "total": sum(sub_types.values()),
        "sub_type_counts": dict(sub_types),
        "empty_answer_count": empty_answer_count,
        "long_answer_count": long_answer_failures,
        "top_failing_samples": Counter(sample_failures).most_common(10),
    }


def analyze_comparison_failures(cases: list[dict[str, Any]]) -> dict[str, Any]:
    sub_types: Counter[str] = Counter()
    completeness_scores: list[float] = []
    for case in cases:
        ft = _failure_type(case)
        if not ft.startswith("comparison"):
            continue
        sub_types[ft] += 1
        ctx = _payload(case).get("context", {})
        c = ctx.get("completeness")
        if c is not None:
            try:
                completeness_scores.append(float(c))
            except (TypeError, ValueError):
                pass
    summary = {"total": sum(sub_types.values()), "sub_type_counts": dict(sub_types)}
    if completeness_scores:
        summary["mean_completeness_in_failures"] = sum(completeness_scores) / len(
            completeness_scores
        )
    return summary


def top_failure_modes(
    cases: list[dict[str, Any]], n: int = 10
) -> list[tuple[str, int]]:
    counter: Counter[str] = Counter()
    for case in cases:
        ft = _failure_type(case)
        counter[ft] += 1
    return counter.most_common(n)


def build_failure_report(failures_path: Path) -> dict[str, Any]:
    cases = load_failures(failures_path)
    return {
        "total_failures": len(cases),
        "top_failure_modes": top_failure_modes(cases),
        "retrieval": analyze_retrieval_failures(cases),
        "qa": analyze_qa_failures(cases),
        "comparison": analyze_comparison_failures(cases),
    }


def render_markdown_report(report: dict[str, Any]) -> str:
    lines = ["# Failure Analysis Report", ""]
    lines.append(f"**Total failures**: {report['total_failures']}")
    lines.append("")
    lines.append("## Top Failure Modes")
    lines.append("")
    if report["top_failure_modes"]:
        lines.append("| Failure Type | Count |")
        lines.append("|---|---|")
        for ft, count in report["top_failure_modes"]:
            lines.append(f"| {ft} | {count} |")
    else:
        lines.append("_No failure cases recorded._")
    lines.append("")

    for section_name, section_data in (
        ("Retrieval", report.get("retrieval", {})),
        ("QA", report.get("qa", {})),
        ("Comparison", report.get("comparison", {})),
    ):
        lines.append(f"## {section_name} Failures")
        lines.append("")
        if not section_data or section_data.get("total", 0) == 0:
            lines.append("_None recorded._")
            lines.append("")
            continue
        lines.append(f"- Total: **{section_data.get('total', 0)}**")
        sub_types = section_data.get("sub_type_counts", {})
        if sub_types:
            lines.append("- Sub-types:")
            for ft, count in sub_types.items():
                lines.append(f"  - {ft}: {count}")
        if section_name == "Retrieval" and section_data.get("by_paper"):
            lines.append("- By paper:")
            for paper, count in section_data["by_paper"].items():
                lines.append(f"  - {paper}: {count}")
        if section_name == "Retrieval" and section_data.get("top_query_words"):
            lines.append("- Frequent query tokens:")
            for word, count in section_data["top_query_words"]:
                lines.append(f"  - `{word}`: {count}")
        if section_name == "QA":
            lines.append(
                f"- Empty-answer failures: {section_data.get('empty_answer_count', 0)}"
            )
            lines.append(
                f"- Long-answer failures (>800 chars): {section_data.get('long_answer_count', 0)}"
            )
        lines.append("")

    lines.append("## Optimization Suggestions")
    lines.append("")
    suggestions = _suggest_optimizations(report)
    for s in suggestions:
        lines.append(f"- {s}")
    if not suggestions:
        lines.append(
            "_No specific suggestions at this volume; collect more failure data._"
        )
    return "\n".join(lines)


def _suggest_optimizations(report: dict[str, Any]) -> list[str]:
    suggestions: list[str] = []
    r = report.get("retrieval", {})
    if r.get("sub_type_counts", {}).get("retrieval_no_results", 0) > 0:
        suggestions.append(
            "Increase retrieval recall: try smaller chunk_size, add hybrid (BM25) retrieval, or expand embedding model."
        )
    if r.get("sub_type_counts", {}).get("retrieval_low_score", 0) > 0:
        suggestions.append(
            "Add a reranker (Phase 4) to lift top-K relevance, and tune the score threshold."
        )
    q = report.get("qa", {})
    if q.get("sub_type_counts", {}).get("qa_empty_answer", 0) > 0:
        suggestions.append(
            "Audit LLM error handling — empty answers often hide silent client closures."
        )
    if q.get("sub_type_counts", {}).get("qa_low_score", 0) > 0:
        suggestions.append(
            "Tighten the QA prompt with explicit citation requirements and few-shot exemplars."
        )
    if q.get("sub_type_counts", {}).get("qa_bad_citation", 0) > 0:
        suggestions.append(
            "Improve citation post-processing — verify each cited section actually appears in the retrieved chunks."
        )
    c = report.get("comparison", {})
    if c.get("sub_type_counts", {}).get("comparison_incomplete", 0) > 0:
        suggestions.append(
            "Reduce comparison aspect count or feed structured summaries to improve completeness."
        )
    return suggestions


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Analyze failure cases and emit a Markdown report."
    )
    parser.add_argument(
        "--failures", type=Path, default=Path("app/storage/analytics/failures.jsonl")
    )
    parser.add_argument(
        "--output", type=Path, default=Path("app/analytics/reports/failure_analysis.md")
    )
    parser.add_argument(
        "--json-output",
        type=Path,
        default=Path("app/analytics/reports/failure_analysis.json"),
    )
    args = parser.parse_args()

    report = build_failure_report(args.failures)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(render_markdown_report(report), encoding="utf-8")
    args.json_output.parent.mkdir(parents=True, exist_ok=True)
    args.json_output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"Generated failure analysis: {args.output}")
    print(
        json.dumps(
            {
                "total_failures": report["total_failures"],
                "top_failure_modes": report["top_failure_modes"],
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
