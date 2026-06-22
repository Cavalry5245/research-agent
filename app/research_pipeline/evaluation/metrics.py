"""
Evaluation Metrics Calculator

计算 research pipeline 运行结果与 gold annotations 的评估指标。
"""

from typing import Any

from app.research_pipeline.evaluation.seed_loader import SeedQuestion


def calculate_workflow_completion_rate(run_detail: dict[str, Any]) -> float:
    """
    计算 workflow 完成率。

    Args:
        run_detail: Run detail dictionary from store.get_run_detail()

    Returns:
        1.0 if status is "completed", else 0.0
    """
    if run_detail is None:
        return 0.0

    status = run_detail.get("status", "")
    return 1.0 if status == "completed" else 0.0


def calculate_stage_success_rate(run_detail: dict[str, Any]) -> float:
    """
    计算 stage 成功率。

    Args:
        run_detail: Run detail dictionary from store.get_run_detail()

    Returns:
        Percentage of stages with status "completed" (0.0 to 1.0)
    """
    if run_detail is None:
        return 0.0

    stages = run_detail.get("stages", [])
    if not stages:
        return 0.0

    completed_count = sum(1 for stage in stages if stage.get("status") == "completed")
    return completed_count / len(stages)


def calculate_claim_verification_coverage(report_claims: list[dict[str, Any]]) -> float:
    """
    计算 claim 验证覆盖率。

    Args:
        report_claims: List of report claims from store.get_claims()

    Returns:
        Percentage of claims with verification_status != "unverified" (0.0 to 1.0)
    """
    if not report_claims:
        return 0.0

    verified_count = sum(
        1 for claim in report_claims
        if claim.get("verification_status") != "unverified"
    )
    return verified_count / len(report_claims)


def calculate_unsupported_claim_rate(report_claims: list[dict[str, Any]]) -> float:
    """
    计算 unsupported claim 比率。

    Args:
        report_claims: List of report claims from store.get_claims()

    Returns:
        Percentage of claims with verification_status == "unsupported" (0.0 to 1.0)
    """
    if not report_claims:
        return 0.0

    # Check for "unsupported" status - this appears to be a typo in the data
    # We'll check for common variations
    unsupported_count = sum(
        1 for claim in report_claims
        if claim.get("verification_status") in ["unsupported", "weak", "conflict_detected"]
    )
    return unsupported_count / len(report_claims)


def calculate_report_point_recall(
    report_markdown: str,
    gold_report_points: list[Any],  # list[GoldReportPoint]
) -> float:
    """
    计算 report point 召回率。

    Args:
        report_markdown: The actual report markdown text
        gold_report_points: List of GoldReportPoint from seed dataset

    Returns:
        Percentage of gold report points mentioned in the report (0.0 to 1.0)
    """
    if not gold_report_points:
        return 0.0

    if not report_markdown:
        return 0.0

    # Simple substring matching - check if each gold point appears in report
    # In production, this would use semantic similarity
    report_lower = report_markdown.lower()

    matched_count = 0
    for gold_point in gold_report_points:
        point_text = gold_point.point.lower() if hasattr(gold_point, 'point') else str(gold_point).lower()
        # Match if any significant keywords from the point appear
        # For MVP, we use simple substring matching
        if point_text in report_lower:
            matched_count += 1

    return matched_count / len(gold_report_points)


def calculate_gold_claim_coverage(
    report_claims: list[dict[str, Any]],
    gold_claims: list[Any],  # list[GoldClaim]
) -> float:
    """
    计算 gold claim 覆盖率。

    Args:
        report_claims: List of report claims from store.get_claims()
        gold_claims: List of GoldClaim from seed dataset

    Returns:
        Percentage of gold claims found in actual report claims (0.0 to 1.0)
    """
    if not gold_claims:
        return 0.0

    if not report_claims:
        return 0.0

    # Extract actual claim texts
    actual_claims_lower = [
        claim.get("claim_text", "").lower()
        for claim in report_claims
    ]

    matched_count = 0
    for gold_claim in gold_claims:
        gold_text = gold_claim.claim.lower() if hasattr(gold_claim, 'claim') else str(gold_claim).lower()

        # Check if any actual claim contains the gold claim (or vice versa)
        for actual_claim in actual_claims_lower:
            if gold_text in actual_claim or actual_claim in gold_text:
                matched_count += 1
                break

    return matched_count / len(gold_claims)


def calculate_metrics(
    run_detail: dict[str, Any],
    report_claims: list[dict[str, Any]],
    gold_seed: SeedQuestion,
    report_markdown: str = "",
) -> dict[str, float | None]:
    """
    计算所有评估指标。

    Args:
        run_detail: Run detail from store.get_run_detail()
        report_claims: Report claims from store.get_claims()
        gold_seed: Gold seed question with annotations
        report_markdown: Report markdown content

    Returns:
        Dictionary with all metrics:
        {
            "workflow_completion_rate": float,
            "stage_success_rate": float,
            "claim_verification_coverage": float | None,
            "unsupported_claim_rate": float | None,
            "report_point_recall": float | None,
            "gold_claim_coverage": float | None,
        }
    """
    metrics = {}

    # Always calculate workflow and stage metrics
    metrics["workflow_completion_rate"] = calculate_workflow_completion_rate(run_detail)
    metrics["stage_success_rate"] = calculate_stage_success_rate(run_detail)

    # Claim-based metrics (None if no claims)
    if report_claims:
        metrics["claim_verification_coverage"] = calculate_claim_verification_coverage(report_claims)
        metrics["unsupported_claim_rate"] = calculate_unsupported_claim_rate(report_claims)
        metrics["gold_claim_coverage"] = calculate_gold_claim_coverage(
            report_claims, gold_seed.gold_claims
        )
    else:
        metrics["claim_verification_coverage"] = None
        metrics["unsupported_claim_rate"] = None
        metrics["gold_claim_coverage"] = None

    # Report point recall (None if no report)
    if report_markdown:
        metrics["report_point_recall"] = calculate_report_point_recall(
            report_markdown, gold_seed.gold_report_points
        )
    else:
        metrics["report_point_recall"] = None

    return metrics


def format_metrics_summary(metrics: dict[str, float | None]) -> str:
    """
    格式化指标为 Markdown 摘要。

    Args:
        metrics: Metrics dictionary from calculate_metrics()

    Returns:
        Markdown formatted summary
    """
    lines = [
        "# Evaluation Metrics Summary",
        "",
        "## Workflow Metrics",
        f"- **Workflow Completion Rate**: {metrics['workflow_completion_rate']:.2%}",
        f"- **Stage Success Rate**: {metrics['stage_success_rate']:.2%}",
        "",
        "## Claim Quality Metrics",
    ]

    if metrics["claim_verification_coverage"] is not None:
        lines.append(f"- **Claim Verification Coverage**: {metrics['claim_verification_coverage']:.2%}")
    else:
        lines.append("- **Claim Verification Coverage**: N/A (no claims)")

    if metrics["unsupported_claim_rate"] is not None:
        lines.append(f"- **Unsupported Claim Rate**: {metrics['unsupported_claim_rate']:.2%}")
    else:
        lines.append("- **Unsupported Claim Rate**: N/A (no claims)")

    if metrics["gold_claim_coverage"] is not None:
        lines.append(f"- **Gold Claim Coverage**: {metrics['gold_claim_coverage']:.2%}")
    else:
        lines.append("- **Gold Claim Coverage**: N/A (no claims)")

    lines.extend([
        "",
        "## Report Quality Metrics",
    ])

    if metrics["report_point_recall"] is not None:
        lines.append(f"- **Report Point Recall**: {metrics['report_point_recall']:.2%}")
    else:
        lines.append("- **Report Point Recall**: N/A (no report)")

    return "\n".join(lines)
