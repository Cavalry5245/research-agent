"""
MVP Gate Report Script

一键生成 MVP gate report，判断 research pipeline 是否达到 demo 标准。

MVP Gate 条件 (PRD 10.3):
1. Completion: ≥2/3 seed questions 达到 "completed" 状态
2. Time to report: 单个 run 默认在 10 分钟内产出报告（中位数 < 300 秒）
3. Reader paper count: 至少 5 篇论文进入 Reader（中位数 ≥ 3）
4. Claim verification coverage: 100% key claims 有 verification status（平均 ≥ 60%）
"""

import json
import statistics
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.research_pipeline.evaluation.metrics import (
    calculate_claim_verification_coverage,
    calculate_workflow_completion_rate,
)
from app.research_pipeline.evaluation.seed_loader import (
    SeedDataset,
    load_seed_dataset,
)
from app.research_pipeline.store import (
    get_claims,
    get_paper_cards,
    get_report,
    get_run_detail,
)


def calculate_time_to_report(run_detail: dict[str, Any]) -> float | None:
    """
    计算 run 从开始到完成的时间（秒）。

    Args:
        run_detail: Run detail from store.get_run_detail()

    Returns:
        Time in seconds, or None if not applicable
    """
    if run_detail is None:
        return None

    started_at = run_detail.get("started_at")
    completed_at = run_detail.get("completed_at")

    if not started_at or not completed_at:
        return None

    try:
        start_time = datetime.fromisoformat(started_at)
        end_time = datetime.fromisoformat(completed_at)
        delta = end_time - start_time
        return delta.total_seconds()
    except (ValueError, TypeError):
        return None


def calculate_reader_paper_count(run_detail: dict[str, Any]) -> int:
    """
    计算进入 Reader 的论文数量。

    Args:
        run_detail: Run detail from store.get_run_detail()

    Returns:
        Number of paper cards (papers that entered reader)
    """
    if run_detail is None:
        return 0

    cards = run_detail.get("cards", [])
    return len(cards)


def evaluate_single_run(
    db_path: str,
    run_id: str,
) -> dict[str, Any]:
    """
    评估单个 run。

    Args:
        db_path: Database path
        run_id: Run ID

    Returns:
        Evaluation result dictionary with metrics
    """
    run_detail = get_run_detail(db_path, run_id)
    report_claims = get_claims(db_path, run_id)

    # Calculate metrics
    completion_rate = calculate_workflow_completion_rate(run_detail)
    time_to_report = calculate_time_to_report(run_detail)
    reader_paper_count = calculate_reader_paper_count(run_detail)
    claim_verification_coverage = calculate_claim_verification_coverage(report_claims) if report_claims else None

    return {
        "run_id": run_id,
        "status": run_detail.get("status") if run_detail else "unknown",
        "completion_rate": completion_rate,
        "time_to_report": time_to_report,
        "reader_paper_count": reader_paper_count,
        "claim_verification_coverage": claim_verification_coverage,
        "total_claims": len(report_claims),
    }


def check_mvp_gate(
    run_results: list[dict[str, Any]],
) -> dict[str, Any]:
    """
    检查是否通过 MVP gate 条件。

    MVP Gate 条件:
    1. Completion: ≥2/3 runs 达到 "completed" 状态
    2. Time to report: 中位数 < 300 秒
    3. Reader paper count: 中位数 ≥ 3
    4. Claim verification coverage: 平均 ≥ 60%

    Args:
        run_results: List of evaluation results from evaluate_single_run()

    Returns:
        Gate check result with pass/fail and reasons
    """
    if not run_results:
        return {
            "passed": False,
            "reason": "No runs to evaluate",
            "conditions": {},
        }

    total_runs = len(run_results)
    completed_runs = sum(1 for r in run_results if r["completion_rate"] == 1.0)

    # Condition 1: Completion rate
    completion_threshold = (2 / 3) * total_runs
    completion_passed = completed_runs >= completion_threshold

    # Condition 2: Time to report (median)
    valid_times = [r["time_to_report"] for r in run_results if r["time_to_report"] is not None]
    if valid_times:
        median_time = statistics.median(valid_times)
        time_passed = median_time < 300.0
    else:
        median_time = None
        time_passed = False

    # Condition 3: Reader paper count (median)
    reader_counts = [r["reader_paper_count"] for r in run_results]
    if reader_counts:
        median_reader_count = statistics.median(reader_counts)
        reader_passed = median_reader_count >= 3
    else:
        median_reader_count = 0
        reader_passed = False

    # Condition 4: Claim verification coverage (mean)
    valid_coverages = [
        r["claim_verification_coverage"]
        for r in run_results
        if r["claim_verification_coverage"] is not None
    ]
    if valid_coverages:
        mean_coverage = statistics.mean(valid_coverages)
        coverage_passed = mean_coverage >= 0.6
    else:
        mean_coverage = None
        coverage_passed = False

    # Overall gate status
    all_passed = completion_passed and time_passed and reader_passed and coverage_passed

    conditions = {
        "completion": {
            "passed": completion_passed,
            "value": f"{completed_runs}/{total_runs}",
            "threshold": f"≥{int(completion_threshold)}/{total_runs}",
            "detail": f"{completed_runs} out of {total_runs} runs completed",
        },
        "time_to_report": {
            "passed": time_passed,
            "value": f"{median_time:.1f}s" if median_time is not None else "N/A",
            "threshold": "<300s",
            "detail": f"Median time: {median_time:.1f}s" if median_time is not None else "No timing data",
        },
        "reader_paper_count": {
            "passed": reader_passed,
            "value": f"{median_reader_count:.0f}",
            "threshold": "≥3",
            "detail": f"Median papers read: {median_reader_count:.0f}",
        },
        "claim_verification_coverage": {
            "passed": coverage_passed,
            "value": f"{mean_coverage:.1%}" if mean_coverage is not None else "N/A",
            "threshold": "≥60%",
            "detail": f"Mean coverage: {mean_coverage:.1%}" if mean_coverage is not None else "No claim data",
        },
    }

    # Build failure reasons
    reasons = []
    if not completion_passed:
        reasons.append(f"Completion rate below threshold: {completed_runs}/{total_runs} < {completion_threshold:.0f}")
    if not time_passed:
        if median_time is not None:
            reasons.append(f"Time to report too slow: {median_time:.1f}s ≥ 300s")
        else:
            reasons.append("Time to report: no timing data available")
    if not reader_passed:
        reasons.append(f"Reader paper count below threshold: {median_reader_count:.0f} < 3")
    if not coverage_passed:
        if mean_coverage is not None:
            reasons.append(f"Claim verification coverage below threshold: {mean_coverage:.1%} < 60%")
        else:
            reasons.append("Claim verification coverage: no claim data available")

    return {
        "passed": all_passed,
        "reason": "; ".join(reasons) if reasons else "All conditions passed",
        "conditions": conditions,
    }


def generate_mvp_gate_report(
    db_path: str,
    run_ids: list[str],
    seed_dataset_path: str | None = None,
    output_json_path: str | None = None,
    output_md_path: str | None = None,
) -> dict[str, Any]:
    """
    生成 MVP gate report。

    Args:
        db_path: Database path
        run_ids: List of run IDs to evaluate
        seed_dataset_path: Optional path to seed dataset JSONL file
        output_json_path: Optional path to write JSON report
        output_md_path: Optional path to write Markdown report

    Returns:
        Full gate report dictionary
    """
    # Load seed dataset if provided
    seed_dataset = None
    if seed_dataset_path:
        try:
            seed_dataset = load_seed_dataset(seed_dataset_path)
        except Exception as e:
            seed_dataset = None
            print(f"Warning: Could not load seed dataset: {e}")

    # Evaluate all runs
    run_results = []
    for run_id in run_ids:
        try:
            result = evaluate_single_run(db_path, run_id)
            run_results.append(result)
        except Exception as e:
            print(f"Warning: Could not evaluate run {run_id}: {e}")

    # Check MVP gate
    gate_check = check_mvp_gate(run_results)

    # Build report
    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "total_runs": len(run_results),
        "seed_questions": len(seed_dataset.questions) if seed_dataset else None,
        "gate_status": "PASSED" if gate_check["passed"] else "FAILED",
        "gate_check": gate_check,
        "run_results": run_results,
    }

    # Write JSON output
    if output_json_path:
        output_path = Path(output_json_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with output_path.open("w", encoding="utf-8") as f:
            json.dump(report, f, indent=2, ensure_ascii=False)

    # Write Markdown output
    if output_md_path:
        md_content = format_markdown_report(report)
        output_path = Path(output_md_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with output_path.open("w", encoding="utf-8") as f:
            f.write(md_content)

    return report


def format_markdown_report(report: dict[str, Any]) -> str:
    """
    格式化 Markdown 报告。

    Args:
        report: Report dictionary from generate_mvp_gate_report()

    Returns:
        Markdown formatted report
    """
    lines = [
        "# Research Pipeline MVP Gate Report",
        "",
        f"**Generated:** {report['generated_at']}",
        "",
        f"**Gate Status:** {'✅ PASSED' if report['gate_status'] == 'PASSED' else '❌ FAILED'}",
        "",
    ]

    # Gate conditions
    lines.extend([
        "## MVP Gate Conditions",
        "",
    ])

    gate_check = report["gate_check"]
    for condition_name, condition_data in gate_check["conditions"].items():
        status_icon = "✅" if condition_data["passed"] else "❌"
        lines.append(
            f"- {status_icon} **{condition_name.replace('_', ' ').title()}**: "
            f"{condition_data['value']} (threshold: {condition_data['threshold']})"
        )
        lines.append(f"  - {condition_data['detail']}")

    if not gate_check["passed"]:
        lines.extend([
            "",
            "## Failure Reasons",
            "",
            gate_check["reason"],
        ])

    # Run results summary
    lines.extend([
        "",
        "## Run Results Summary",
        "",
        f"**Total Runs:** {report['total_runs']}",
        "",
        "| Run ID | Status | Time (s) | Papers Read | Claims | Coverage |",
        "|--------|--------|----------|-------------|--------|----------|",
    ])

    for run_result in report["run_results"]:
        run_id = run_result["run_id"]
        status = run_result["status"]
        time_str = f"{run_result['time_to_report']:.1f}" if run_result["time_to_report"] else "N/A"
        papers = run_result["reader_paper_count"]
        claims = run_result["total_claims"]
        coverage_str = (
            f"{run_result['claim_verification_coverage']:.1%}"
            if run_result["claim_verification_coverage"] is not None
            else "N/A"
        )
        lines.append(f"| {run_id} | {status} | {time_str} | {papers} | {claims} | {coverage_str} |")

    lines.extend([
        "",
        "---",
        "",
        "_This report was generated automatically by the Research Pipeline evaluation harness._",
    ])

    return "\n".join(lines)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Generate MVP gate report for research pipeline")
    parser.add_argument("--db-path", required=True, help="Path to SQLite database")
    parser.add_argument("--run-ids", nargs="+", required=True, help="List of run IDs to evaluate")
    parser.add_argument("--seed-dataset", help="Path to seed dataset JSONL file")
    parser.add_argument("--output-json", help="Path to write JSON report")
    parser.add_argument("--output-md", help="Path to write Markdown report")

    args = parser.parse_args()

    report = generate_mvp_gate_report(
        db_path=args.db_path,
        run_ids=args.run_ids,
        seed_dataset_path=args.seed_dataset,
        output_json_path=args.output_json,
        output_md_path=args.output_md,
    )

    print(f"\nGate Status: {report['gate_status']}")
    print(f"Total Runs: {report['total_runs']}")
    if not report["gate_check"]["passed"]:
        print(f"\nFailure Reason: {report['gate_check']['reason']}")
