"""
Tests for Evaluation Metrics Calculator
"""

import pytest

from app.research_pipeline.evaluation.metrics import (
    calculate_claim_verification_coverage,
    calculate_gold_claim_coverage,
    calculate_metrics,
    calculate_report_point_recall,
    calculate_stage_success_rate,
    calculate_unsupported_claim_rate,
    calculate_workflow_completion_rate,
    format_metrics_summary,
)
from app.research_pipeline.evaluation.seed_loader import (
    GoldClaim,
    GoldReportPoint,
    SeedQuestion,
    GoldPaper,
)


class TestWorkflowCompletionRate:
    """Test workflow_completion_rate metric"""

    def test_completed_run(self):
        """Test completed run returns 1.0"""
        run_detail = {"status": "completed"}
        assert calculate_workflow_completion_rate(run_detail) == 1.0

    def test_failed_run(self):
        """Test failed run returns 0.0"""
        run_detail = {"status": "failed"}
        assert calculate_workflow_completion_rate(run_detail) == 0.0

    def test_running_run(self):
        """Test running run returns 0.0"""
        run_detail = {"status": "running"}
        assert calculate_workflow_completion_rate(run_detail) == 0.0

    def test_degraded_run(self):
        """Test degraded run returns 0.0"""
        run_detail = {"status": "degraded"}
        assert calculate_workflow_completion_rate(run_detail) == 0.0

    def test_none_run(self):
        """Test None run returns 0.0"""
        assert calculate_workflow_completion_rate(None) == 0.0

    def test_empty_run(self):
        """Test empty dict returns 0.0"""
        assert calculate_workflow_completion_rate({}) == 0.0


class TestStageSuccessRate:
    """Test stage_success_rate metric"""

    def test_all_stages_completed(self):
        """Test all stages completed returns 1.0"""
        run_detail = {
            "stages": [
                {"stage": "planner", "status": "completed"},
                {"stage": "retriever", "status": "completed"},
                {"stage": "reader", "status": "completed"},
                {"stage": "synthesis", "status": "completed"},
                {"stage": "harness", "status": "completed"},
            ]
        }
        assert calculate_stage_success_rate(run_detail) == 1.0

    def test_partial_completion(self):
        """Test partial completion returns correct ratio"""
        run_detail = {
            "stages": [
                {"stage": "planner", "status": "completed"},
                {"stage": "retriever", "status": "completed"},
                {"stage": "reader", "status": "failed"},
                {"stage": "synthesis", "status": "completed"},
                {"stage": "harness", "status": "queued"},
            ]
        }
        assert calculate_stage_success_rate(run_detail) == 0.6  # 3/5

    def test_no_stages_completed(self):
        """Test no stages completed returns 0.0"""
        run_detail = {
            "stages": [
                {"stage": "planner", "status": "failed"},
                {"stage": "retriever", "status": "failed"},
            ]
        }
        assert calculate_stage_success_rate(run_detail) == 0.0

    def test_empty_stages(self):
        """Test empty stages list returns 0.0"""
        run_detail = {"stages": []}
        assert calculate_stage_success_rate(run_detail) == 0.0

    def test_none_run(self):
        """Test None run returns 0.0"""
        assert calculate_stage_success_rate(None) == 0.0

    def test_missing_stages_key(self):
        """Test missing stages key returns 0.0"""
        assert calculate_stage_success_rate({}) == 0.0


class TestClaimVerificationCoverage:
    """Test claim_verification_coverage metric"""

    def test_all_verified(self):
        """Test all claims verified returns 1.0"""
        claims = [
            {"claim_text": "Claim 1", "verification_status": "supported"},
            {"claim_text": "Claim 2", "verification_status": "weak"},
            {"claim_text": "Claim 3", "verification_status": "conflict_detected"},
        ]
        assert calculate_claim_verification_coverage(claims) == 1.0

    def test_partial_verification(self):
        """Test partial verification returns correct ratio"""
        claims = [
            {"claim_text": "Claim 1", "verification_status": "supported"},
            {"claim_text": "Claim 2", "verification_status": "unverified"},
            {"claim_text": "Claim 3", "verification_status": "weak"},
            {"claim_text": "Claim 4", "verification_status": "unverified"},
        ]
        assert calculate_claim_verification_coverage(claims) == 0.5  # 2/4

    def test_all_unverified(self):
        """Test all unverified returns 0.0"""
        claims = [
            {"claim_text": "Claim 1", "verification_status": "unverified"},
            {"claim_text": "Claim 2", "verification_status": "unverified"},
        ]
        assert calculate_claim_verification_coverage(claims) == 0.0

    def test_empty_claims(self):
        """Test empty claims list returns 0.0"""
        assert calculate_claim_verification_coverage([]) == 0.0


class TestUnsupportedClaimRate:
    """Test unsupported_claim_rate metric"""

    def test_no_unsupported_claims(self):
        """Test no unsupported claims returns 0.0"""
        claims = [
            {"claim_text": "Claim 1", "verification_status": "supported"},
            {"claim_text": "Claim 2", "verification_status": "supported"},
        ]
        assert calculate_unsupported_claim_rate(claims) == 0.0

    def test_all_unsupported_claims(self):
        """Test all unsupported claims returns 1.0"""
        claims = [
            {"claim_text": "Claim 1", "verification_status": "weak"},
            {"claim_text": "Claim 2", "verification_status": "conflict_detected"},
        ]
        assert calculate_unsupported_claim_rate(claims) == 1.0

    def test_partial_unsupported(self):
        """Test partial unsupported returns correct ratio"""
        claims = [
            {"claim_text": "Claim 1", "verification_status": "supported"},
            {"claim_text": "Claim 2", "verification_status": "weak"},
            {"claim_text": "Claim 3", "verification_status": "supported"},
            {"claim_text": "Claim 4", "verification_status": "conflict_detected"},
        ]
        assert calculate_unsupported_claim_rate(claims) == 0.5  # 2/4

    def test_empty_claims(self):
        """Test empty claims list returns 0.0"""
        assert calculate_unsupported_claim_rate([]) == 0.0


class TestReportPointRecall:
    """Test report_point_recall metric"""

    def test_all_points_found(self):
        """Test all report points found returns 1.0"""
        report = "This report discusses attention mechanisms and transformer architecture."
        gold_points = [
            GoldReportPoint(
                point="attention mechanisms",
                expected_section="method_comparison",
            ),
            GoldReportPoint(
                point="transformer architecture",
                expected_section="method_comparison",
            ),
        ]
        assert calculate_report_point_recall(report, gold_points) == 1.0

    def test_partial_points_found(self):
        """Test partial points found returns correct ratio"""
        report = "This report discusses attention mechanisms."
        gold_points = [
            GoldReportPoint(
                point="attention mechanisms",
                expected_section="method_comparison",
            ),
            GoldReportPoint(
                point="transformer architecture",
                expected_section="method_comparison",
            ),
        ]
        assert calculate_report_point_recall(report, gold_points) == 0.5

    def test_no_points_found(self):
        """Test no points found returns 0.0"""
        report = "This report discusses something else."
        gold_points = [
            GoldReportPoint(
                point="attention mechanisms",
                expected_section="method_comparison",
            ),
        ]
        assert calculate_report_point_recall(report, gold_points) == 0.0

    def test_empty_report(self):
        """Test empty report returns 0.0"""
        gold_points = [
            GoldReportPoint(
                point="attention mechanisms",
                expected_section="method_comparison",
            ),
        ]
        assert calculate_report_point_recall("", gold_points) == 0.0

    def test_empty_gold_points(self):
        """Test empty gold points returns 0.0"""
        assert calculate_report_point_recall("Some report", []) == 0.0

    def test_case_insensitive_matching(self):
        """Test matching is case insensitive"""
        report = "This report discusses ATTENTION MECHANISMS."
        gold_points = [
            GoldReportPoint(
                point="attention mechanisms",
                expected_section="method_comparison",
            ),
        ]
        assert calculate_report_point_recall(report, gold_points) == 1.0


class TestGoldClaimCoverage:
    """Test gold_claim_coverage metric"""

    def test_all_gold_claims_covered(self):
        """Test all gold claims covered returns 1.0"""
        report_claims = [
            {"claim_text": "The model achieves 95% accuracy"},
            {"claim_text": "Training took 3 days"},
        ]
        gold_claims = [
            GoldClaim(
                claim="The model achieves 95% accuracy",
                paper_id="paper1",
                evidence_snippet="We achieved 95% accuracy",
            ),
            GoldClaim(
                claim="Training took 3 days",
                paper_id="paper1",
                evidence_snippet="Training time was 3 days",
            ),
        ]
        assert calculate_gold_claim_coverage(report_claims, gold_claims) == 1.0

    def test_partial_gold_claims_covered(self):
        """Test partial gold claims covered returns correct ratio"""
        report_claims = [
            {"claim_text": "The model achieves 95% accuracy on ImageNet"},
        ]
        gold_claims = [
            GoldClaim(
                claim="The model achieves 95% accuracy",
                paper_id="paper1",
                evidence_snippet="We achieved 95% accuracy",
            ),
            GoldClaim(
                claim="Training took 3 days",
                paper_id="paper1",
                evidence_snippet="Training time was 3 days",
            ),
        ]
        assert calculate_gold_claim_coverage(report_claims, gold_claims) == 0.5

    def test_no_gold_claims_covered(self):
        """Test no gold claims covered returns 0.0"""
        report_claims = [
            {"claim_text": "Something completely different"},
        ]
        gold_claims = [
            GoldClaim(
                claim="The model achieves 95% accuracy",
                paper_id="paper1",
                evidence_snippet="We achieved 95% accuracy",
            ),
        ]
        assert calculate_gold_claim_coverage(report_claims, gold_claims) == 0.0

    def test_empty_report_claims(self):
        """Test empty report claims returns 0.0"""
        gold_claims = [
            GoldClaim(
                claim="The model achieves 95% accuracy",
                paper_id="paper1",
                evidence_snippet="We achieved 95% accuracy",
            ),
        ]
        assert calculate_gold_claim_coverage([], gold_claims) == 0.0

    def test_empty_gold_claims(self):
        """Test empty gold claims returns 0.0"""
        report_claims = [
            {"claim_text": "Some claim"},
        ]
        assert calculate_gold_claim_coverage(report_claims, []) == 0.0

    def test_substring_matching(self):
        """Test substring matching works"""
        report_claims = [
            {"claim_text": "The transformer model achieves 95% accuracy on ImageNet"},
        ]
        gold_claims = [
            GoldClaim(
                claim="achieves 95% accuracy",
                paper_id="paper1",
                evidence_snippet="We achieved 95% accuracy",
            ),
        ]
        assert calculate_gold_claim_coverage(report_claims, gold_claims) == 1.0


class TestCalculateMetrics:
    """Test calculate_metrics integration"""

    def test_complete_successful_run(self):
        """Test metrics for a complete successful run"""
        run_detail = {
            "status": "completed",
            "stages": [
                {"stage": "planner", "status": "completed"},
                {"stage": "retriever", "status": "completed"},
                {"stage": "reader", "status": "completed"},
                {"stage": "synthesis", "status": "completed"},
                {"stage": "harness", "status": "completed"},
            ],
        }

        report_claims = [
            {"claim_text": "accuracy is 95%", "verification_status": "supported"},
            {"claim_text": "training took 3 days", "verification_status": "weak"},
        ]

        gold_seed = SeedQuestion(
            question="Test question",
            gold_papers=[
                GoldPaper(
                    title="Paper 1",
                    doi="10.1234/test",
                    relevance=3,
                    reason="Key paper",
                )
                for _ in range(5)
            ],
            gold_report_points=[
                GoldReportPoint(
                    point="accuracy is 95%",
                    expected_section="results",
                )
                for _ in range(5)
            ],
            gold_claims=[
                GoldClaim(
                    claim="accuracy is 95%",
                    paper_id="paper1",
                    evidence_snippet="We achieved 95%",
                )
                for _ in range(5)
            ],
        )

        report_markdown = "The model accuracy is 95% on the test set."

        metrics = calculate_metrics(run_detail, report_claims, gold_seed, report_markdown)

        assert metrics["workflow_completion_rate"] == 1.0
        assert metrics["stage_success_rate"] == 1.0
        assert metrics["claim_verification_coverage"] == 1.0
        assert metrics["unsupported_claim_rate"] == 0.5
        assert metrics["report_point_recall"] == 1.0
        assert metrics["gold_claim_coverage"] == 1.0

    def test_failed_run_no_claims(self):
        """Test metrics for a failed run with no claims"""
        run_detail = {
            "status": "failed",
            "stages": [
                {"stage": "planner", "status": "completed"},
                {"stage": "retriever", "status": "failed"},
                {"stage": "reader", "status": "queued"},
                {"stage": "synthesis", "status": "queued"},
                {"stage": "harness", "status": "queued"},
            ],
        }

        report_claims = []

        gold_seed = SeedQuestion(
            question="Test question",
            gold_papers=[
                GoldPaper(
                    title="Paper 1",
                    doi="10.1234/test",
                    relevance=3,
                    reason="Key paper",
                )
                for _ in range(5)
            ],
            gold_report_points=[
                GoldReportPoint(
                    point="some point",
                    expected_section="results",
                )
                for _ in range(5)
            ],
            gold_claims=[
                GoldClaim(
                    claim="some claim",
                    paper_id="paper1",
                    evidence_snippet="evidence",
                )
                for _ in range(5)
            ],
        )

        report_markdown = ""

        metrics = calculate_metrics(run_detail, report_claims, gold_seed, report_markdown)

        assert metrics["workflow_completion_rate"] == 0.0
        assert metrics["stage_success_rate"] == 0.2  # 1/5
        assert metrics["claim_verification_coverage"] is None
        assert metrics["unsupported_claim_rate"] is None
        assert metrics["report_point_recall"] is None
        assert metrics["gold_claim_coverage"] is None

    def test_degraded_run_with_partial_claims(self):
        """Test metrics for a degraded run with partial claims"""
        run_detail = {
            "status": "degraded",
            "stages": [
                {"stage": "planner", "status": "completed"},
                {"stage": "retriever", "status": "completed"},
                {"stage": "reader", "status": "degraded"},
                {"stage": "synthesis", "status": "completed"},
                {"stage": "harness", "status": "completed"},
            ],
        }

        report_claims = [
            {"claim_text": "claim 1", "verification_status": "supported"},
            {"claim_text": "claim 2", "verification_status": "unverified"},
        ]

        gold_seed = SeedQuestion(
            question="Test question",
            gold_papers=[
                GoldPaper(
                    title="Paper 1",
                    doi="10.1234/test",
                    relevance=3,
                    reason="Key paper",
                )
                for _ in range(5)
            ],
            gold_report_points=[
                GoldReportPoint(
                    point="point 1",
                    expected_section="results",
                ),
                GoldReportPoint(
                    point="point 2",
                    expected_section="results",
                ),
                GoldReportPoint(
                    point="point 3",
                    expected_section="results",
                ),
                GoldReportPoint(
                    point="point 4",
                    expected_section="results",
                ),
                GoldReportPoint(
                    point="point 5",
                    expected_section="results",
                ),
            ],
            gold_claims=[
                GoldClaim(
                    claim=f"claim {i}",
                    paper_id="paper1",
                    evidence_snippet="evidence",
                )
                for i in range(1, 6)
            ],
        )

        report_markdown = "This report mentions point 1."

        metrics = calculate_metrics(run_detail, report_claims, gold_seed, report_markdown)

        assert metrics["workflow_completion_rate"] == 0.0
        assert metrics["stage_success_rate"] == 0.8  # 4/5
        assert metrics["claim_verification_coverage"] == 0.5  # 1/2
        assert metrics["unsupported_claim_rate"] == 0.0
        assert metrics["report_point_recall"] == 0.2  # 1/5
        assert metrics["gold_claim_coverage"] == 0.4  # 2/5


class TestFormatMetricsSummary:
    """Test format_metrics_summary function"""

    def test_complete_metrics(self):
        """Test formatting complete metrics"""
        metrics = {
            "workflow_completion_rate": 1.0,
            "stage_success_rate": 0.8,
            "claim_verification_coverage": 0.9,
            "unsupported_claim_rate": 0.1,
            "report_point_recall": 0.75,
            "gold_claim_coverage": 0.85,
        }

        summary = format_metrics_summary(metrics)

        assert "# Evaluation Metrics Summary" in summary
        assert "100.00%" in summary  # workflow completion
        assert "80.00%" in summary  # stage success
        assert "90.00%" in summary  # claim verification
        assert "10.00%" in summary  # unsupported rate
        assert "75.00%" in summary  # report point recall
        assert "85.00%" in summary  # gold claim coverage

    def test_partial_metrics_with_nulls(self):
        """Test formatting metrics with None values"""
        metrics = {
            "workflow_completion_rate": 0.5,
            "stage_success_rate": 0.6,
            "claim_verification_coverage": None,
            "unsupported_claim_rate": None,
            "report_point_recall": None,
            "gold_claim_coverage": None,
        }

        summary = format_metrics_summary(metrics)

        assert "# Evaluation Metrics Summary" in summary
        assert "50.00%" in summary  # workflow completion
        assert "60.00%" in summary  # stage success
        assert "N/A (no claims)" in summary
        assert "N/A (no report)" in summary

    def test_zero_metrics(self):
        """Test formatting zero metrics"""
        metrics = {
            "workflow_completion_rate": 0.0,
            "stage_success_rate": 0.0,
            "claim_verification_coverage": 0.0,
            "unsupported_claim_rate": 0.0,
            "report_point_recall": 0.0,
            "gold_claim_coverage": 0.0,
        }

        summary = format_metrics_summary(metrics)

        assert "# Evaluation Metrics Summary" in summary
        assert "0.00%" in summary
