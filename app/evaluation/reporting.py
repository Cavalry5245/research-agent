from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from app.evaluation.metrics import load_qa_samples

DEFAULT_RETRIEVAL_REPORT = Path(
    "app/evaluation/reports/retrieval_eval_seed_report.json"
)
DEFAULT_DATASET = Path("app/evaluation/datasets/qa_eval_seed.jsonl")
DEFAULT_OUTPUT = Path("app/evaluation/reports/baseline_report.md")
DEFAULT_ENVIRONMENT = "WSL + conda"
DEFAULT_VALIDATION = (
    "Offline deterministic retrieval baseline; real retrieval chain not yet wired."
)


def _load_retrieval_report(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _build_failed_case_samples(
    results: list[dict[str, Any]], limit: int = 3
) -> list[dict[str, Any]]:
    explicit_failures = [result for result in results if not result.get("hit_at_k")]
    selected = explicit_failures[:limit]

    if not selected:
        for result in results[:limit]:
            selected.append(
                {
                    **result,
                    "failure_reason": "No true misses were observed in the deterministic baseline; this sample is included as a calibration placeholder because the current evaluator injects the gold section at rank 1.",
                }
            )
        return selected

    enriched = []
    for result in selected:
        enriched.append(
            {
                **result,
                "failure_reason": "Retriever did not return a relevant chunk within top-k.",
            }
        )
    return enriched


def build_baseline_report_payload(
    retrieval_report_path: Path,
    dataset_path: Path,
    top_k: int,
    environment_summary: str = DEFAULT_ENVIRONMENT,
    validation_summary: str = DEFAULT_VALIDATION,
) -> dict[str, Any]:
    retrieval_report = _load_retrieval_report(retrieval_report_path)
    samples = load_qa_samples(str(dataset_path))
    summary = retrieval_report["summary"]

    unique_papers = {sample.paper_id for sample in samples if sample.paper_id}
    section_labels = sorted(
        {section for sample in samples for section in sample.supporting_sections}
    )

    return {
        "dataset_scale": {
            "qa_sample_count": len(samples),
            "paper_count": len(unique_papers),
            "section_label_count": len(section_labels),
            "dataset_path": str(dataset_path),
        },
        "retrieval_configuration": {
            "top_k": top_k,
            "dataset_report_source": str(retrieval_report_path),
            "retrieval_mode": "deterministic seed baseline",
            "relevant_match_rule": "paper_id must match and section name must align with supporting_sections",
        },
        "metrics": {
            "hit_at_k": summary["hit_rate"],
            "recall_at_k": summary["mean_recall"],
            "mrr": summary["mrr"],
            "metric_top_k": top_k,
        },
        "failed_case_samples": _build_failed_case_samples(retrieval_report["results"]),
        "next_step_recommendations": [
            "Replace the deterministic retrieval stub with the real vector-store retrieval pipeline before using these metrics as product KPIs.",
            "Expand the seed dataset with more papers and harder multi-section questions to reduce metric inflation.",
            "Add true negative and miss cases so failed-case analysis reflects real retriever behavior instead of placeholder calibration examples.",
        ],
        "environment_notes": {
            "environment": environment_summary,
            "validation": validation_summary,
        },
    }


def build_baseline_report_markdown(payload: dict[str, Any]) -> str:
    dataset = payload["dataset_scale"]
    config = payload["retrieval_configuration"]
    metrics = payload["metrics"]
    failed_cases = payload["failed_case_samples"]
    recommendations = payload["next_step_recommendations"]
    environment = payload["environment_notes"]

    top_k = metrics.get("metric_top_k", config["top_k"])
    metric_lines = [
        f"- Hit@{top_k}: {metrics['hit_at_k']:.3f}",
        f"- Recall@{top_k}: {metrics['recall_at_k']:.3f}",
        f"- MRR: {metrics['mrr']:.3f}",
    ]

    failed_case_lines = []
    for case in failed_cases:
        failed_case_lines.extend(
            [
                f"### {case['sample_id']}",
                f"- Query: {case['query']}",
                f"- Hit@k: {case['hit_at_k']}",
                f"- Recall@k: {case['recall_at_k']:.3f}",
                f"- MRR: {case['mrr']:.3f}",
                f"- Failure note: {case['failure_reason']}",
            ]
        )

    recommendation_lines = [
        f"{idx}. {item}" for idx, item in enumerate(recommendations, start=1)
    ]

    return "\n".join(
        [
            "# Retrieval Baseline Report",
            "",
            "## Dataset Scale",
            f"- QA samples: {dataset['qa_sample_count']}",
            f"- Papers covered: {dataset['paper_count']}",
            f"- Supporting-section labels: {dataset['section_label_count']}",
            f"- Dataset path: `{dataset['dataset_path']}`",
            "",
            "## Retrieval Configuration",
            f"- Top-k: {config['top_k']}",
            f"- Retrieval mode: {config['retrieval_mode']}",
            f"- Relevance rule: {config['relevant_match_rule']}",
            f"- Source report: `{config['dataset_report_source']}`",
            "",
            "## Metrics",
            *metric_lines,
            "",
            "## Failed Case Samples",
            *failed_case_lines,
            "",
            "## Next-Step Recommendations",
            *recommendation_lines,
            "",
            "## Environment and Validation Notes",
            f"- Environment: {environment['environment']}",
            f"- Validation: {environment['validation']}",
            "",
        ]
    )


def build_retrieval_upgrade_report_payload(
    comparison_report: dict[str, Any],
) -> dict[str, Any]:
    summary = comparison_report.get("summary", {})
    strategy_summaries = comparison_report.get("strategy_summaries", {})
    results_by_strategy = comparison_report.get("results_by_strategy", {})

    failure_case_samples = {
        strategy: _build_failed_case_samples(results)
        for strategy, results in results_by_strategy.items()
    }

    recommendations = [
        "Replace the deterministic comparison stub with the real vector-store + reranker pipeline so delta metrics reflect production behavior.",
        "Expand the seed dataset with harder lexical-overlap cases to better separate hybrid retrieval from dense-only retrieval.",
        "Add qualitative error analysis for top failure samples to explain when reranking improves ranking and when sparse signals still underperform.",
    ]

    return {
        "overview": {
            "sample_count": summary.get("sample_count", 0),
            "top_k": summary.get("top_k"),
            "baseline_strategy": summary.get("baseline_strategy", "dense"),
            "best_strategy": summary.get("best_strategy"),
            "strategy_count": summary.get("strategy_count", len(strategy_summaries)),
        },
        "strategies": strategy_summaries,
        "improvements": summary.get("improvements", {}),
        "failure_case_samples": failure_case_samples,
        "recommendations": recommendations,
    }


def build_retrieval_upgrade_report_markdown(payload: dict[str, Any]) -> str:
    overview = payload["overview"]
    strategies = payload["strategies"]
    improvements = payload["improvements"]
    failure_case_samples = payload["failure_case_samples"]
    recommendations = payload["recommendations"]

    strategy_lines = []
    for strategy, metrics in strategies.items():
        strategy_lines.extend(
            [
                f"### {strategy}",
                f"- Samples: {metrics['sample_count']}",
                f"- Hit rate: {metrics['hit_rate']:.3f}",
                f"- Mean recall: {metrics['mean_recall']:.3f}",
                f"- MRR: {metrics['mrr']:.3f}",
            ]
        )

    improvement_lines = []
    for strategy, delta in improvements.items():
        improvement_lines.extend(
            [
                f"### {strategy}",
                f"- Δ Hit rate vs dense: {delta['hit_rate_delta_vs_dense']:+.3f}",
                f"- Δ Mean recall vs dense: {delta['mean_recall_delta_vs_dense']:+.3f}",
                f"- Δ MRR vs dense: {delta['mrr_delta_vs_dense']:+.3f}",
            ]
        )

    failure_lines = []
    for strategy, cases in failure_case_samples.items():
        failure_lines.append(f"### {strategy}")
        for case in cases:
            failure_lines.extend(
                [
                    f"- Sample: {case['sample_id']}",
                    f"  - Query: {case['query']}",
                    f"  - Hit@k: {case['hit_at_k']}",
                    f"  - Failure note: {case['failure_reason']}",
                ]
            )

    recommendation_lines = [
        f"{idx}. {item}" for idx, item in enumerate(recommendations, start=1)
    ]

    return "\n".join(
        [
            "# Retrieval Upgrade Report",
            "",
            "## Overview",
            f"- Sample count: {overview['sample_count']}",
            f"- Top-k: {overview['top_k']}",
            f"- Baseline strategy: {overview['baseline_strategy']}",
            f"- Best strategy: {overview['best_strategy']}",
            f"- Strategy count: {overview['strategy_count']}",
            "",
            "## Strategy Metrics",
            *strategy_lines,
            "",
            "## Improvements vs Dense Baseline",
            *improvement_lines,
            "",
            "## Failure Case Samples",
            *failure_lines,
            "",
            "## Next-Step Recommendations",
            *recommendation_lines,
            "",
        ]
    )


def build_comparison_report_payload(report: dict[str, Any]) -> dict[str, Any]:
    summary = report.get("summary", {})
    results = report.get("results", [])

    failure_case_samples = [
        result
        for result in results
        if result.get("missing_aspects")
        or result.get("aspects_with_missing_evidence")
        or result.get("evidence_quality_issues")
        or result.get("section_alignment_issues")
        or not all(result.get("paper_coverage", {}).values())
    ]
    if not failure_case_samples:
        failure_case_samples = results[:3]

    return {
        "overview": {
            "sample_count": summary.get("sample_count", len(results)),
            "mean_completeness": summary.get("mean_completeness", 0.0),
            "mean_evidence_completeness": summary.get(
                "mean_evidence_completeness", 0.0
            ),
            "mean_evidence_quality": summary.get("mean_evidence_quality", 0.0),
            "mean_section_alignment": summary.get("mean_section_alignment", 0.0),
            "mean_paper_balance": summary.get("mean_paper_balance", 0.0),
        },
        "failure_case_samples": failure_case_samples,
        "recommendations": [
            "Connect the evaluator to live compare outputs so completeness and evidence coverage reflect real LLM behavior rather than deterministic stubs.",
            "Expand the comparison seed set with harder aspect combinations and asymmetric evidence cases.",
            "Add aspect-level evidence quality and section-alignment checks to distinguish missing evidence from low-quality but non-empty citations.",
        ],
    }


def build_comparison_report_markdown(payload: dict[str, Any]) -> str:
    overview = payload["overview"]
    failure_case_samples = payload["failure_case_samples"]
    recommendations = payload["recommendations"]

    failure_lines = []
    for case in failure_case_samples:
        missing_aspects = ", ".join(case.get("missing_aspects", [])) or "无"
        missing_evidence = (
            ", ".join(case.get("aspects_with_missing_evidence", [])) or "无"
        )
        evidence_quality_issues = (
            ", ".join(case.get("evidence_quality_issues", [])) or "无"
        )
        section_alignment_issues = (
            ", ".join(case.get("section_alignment_issues", [])) or "无"
        )
        paper_alignment = case.get("paper_alignment", {})
        paper_alignment_display = (
            ", ".join(
                f"{paper_id}={score:.3f}" for paper_id, score in paper_alignment.items()
            )
            or "无"
        )
        paper_alignment_issues = case.get("paper_alignment_issues", {})
        paper_alignment_issue_display = (
            "; ".join(
                f"{aspect}: {', '.join(paper_ids)}"
                for aspect, paper_ids in paper_alignment_issues.items()
            )
            or "无"
        )
        uncovered_papers = (
            ", ".join(
                paper_id
                for paper_id, covered in case.get("paper_coverage", {}).items()
                if not covered
            )
            or "无"
        )
        failure_lines.extend(
            [
                f"### {case['sample_id']}",
                f"- Question: {case['question']}",
                f"- Completeness: {case['completeness']:.3f}",
                f"- Evidence completeness: {case['evidence_completeness']:.3f}",
                f"- Evidence quality: {case.get('evidence_quality', 0.0):.3f}",
                f"- Section alignment: {case.get('section_alignment', 0.0):.3f}",
                f"- Paper balance: {case['paper_balance']:.3f}",
                f"- Comparison source: {case.get('comparison_source', 'unknown')}",
                f"- Uses structured summaries: {case.get('uses_structured_summaries', False)}",
                f"- Missing aspects: {missing_aspects}",
                f"- Missing evidence aspects: {missing_evidence}",
                f"- Evidence quality issues: {evidence_quality_issues}",
                f"- Section alignment issues: {section_alignment_issues}",
                f"- Paper alignment: {paper_alignment_display}",
                f"- Paper alignment issues: {paper_alignment_issue_display}",
                f"- Uncovered papers: {uncovered_papers}",
            ]
        )

    recommendation_lines = [
        f"{idx}. {item}" for idx, item in enumerate(recommendations, start=1)
    ]

    return "\n".join(
        [
            "# Structured Comparison Evaluation Report",
            "",
            "## Summary",
            f"- Sample count: {overview['sample_count']}",
            f"- Mean completeness: {overview['mean_completeness']:.3f}",
            f"- Mean evidence completeness: {overview['mean_evidence_completeness']:.3f}",
            f"- Mean evidence quality: {overview['mean_evidence_quality']:.3f}",
            f"- Mean section alignment: {overview['mean_section_alignment']:.3f}",
            f"- Mean paper balance: {overview['mean_paper_balance']:.3f}",
            "",
            "## Failure Case Samples",
            *failure_lines,
            "",
            "## Next-Step Recommendations",
            *recommendation_lines,
            "",
        ]
    )


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Generate a Markdown baseline report for retrieval evaluation."
    )
    parser.add_argument(
        "--retrieval-report", type=Path, default=DEFAULT_RETRIEVAL_REPORT
    )
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET)
    parser.add_argument("--top-k", type=int, default=3)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--environment", type=str, default=DEFAULT_ENVIRONMENT)
    parser.add_argument("--validation", type=str, default=DEFAULT_VALIDATION)
    args = parser.parse_args()

    payload = build_baseline_report_payload(
        retrieval_report_path=args.retrieval_report,
        dataset_path=args.dataset,
        top_k=args.top_k,
        environment_summary=args.environment,
        validation_summary=args.validation,
    )
    markdown = build_baseline_report_markdown(payload)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(markdown, encoding="utf-8")
    print(f"Generated baseline report: {args.output}")
