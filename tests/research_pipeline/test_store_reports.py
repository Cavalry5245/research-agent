"""
Tests for report store methods.

测试报告持久化和claim汇总功能。
"""

import json
import tempfile
from pathlib import Path

import pytest

from app.research_pipeline import store


@pytest.fixture
def temp_db():
    """Create a temporary test database."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = str(Path(tmpdir) / "test.db")
        store.init_db(db_path)

        # Create a test run
        run_id = store.create_run(
            db_path=db_path,
            question="Test question",
            source_mode="web_search",
            max_reader_papers=5,
            reader_concurrency=2,
        )

        yield db_path, run_id


class TestSaveReport:
    """Test save_report functionality."""

    def test_save_report_creates_new_report(self, temp_db):
        """save_report creates a new report record."""
        db_path, run_id = temp_db

        markdown = "# Test Report\n\n这是测试报告。"
        template_version = "v1.0"

        report_id = store.save_report(
            db_path=db_path,
            run_id=run_id,
            markdown=markdown,
            template_version=template_version,
        )

        assert report_id is not None
        assert report_id.startswith("report_")

    def test_save_report_updates_existing_report(self, temp_db):
        """save_report updates existing report for the same run_id."""
        db_path, run_id = temp_db

        # Save first report
        report_id_1 = store.save_report(
            db_path=db_path,
            run_id=run_id,
            markdown="# First Report",
            template_version="v1.0",
        )

        # Save second report for same run_id
        report_id_2 = store.save_report(
            db_path=db_path,
            run_id=run_id,
            markdown="# Updated Report",
            template_version="v1.1",
        )

        # Should update, not create new
        assert report_id_2 == report_id_1

        # Verify only one report exists
        report = store.get_report(db_path, run_id)
        assert report["markdown"] == "# Updated Report"
        assert report["template_version"] == "v1.1"

    def test_save_report_preserves_utf8_chinese(self, temp_db):
        """save_report preserves UTF-8 Chinese characters without escaping."""
        db_path, run_id = temp_db

        markdown = "# 研究报告\n\n## 方法论\n\n本研究采用深度学习方法。"

        store.save_report(
            db_path=db_path,
            run_id=run_id,
            markdown=markdown,
            template_version="v1.0",
        )

        report = store.get_report(db_path, run_id)
        assert report["markdown"] == markdown
        # Verify Chinese is not escaped like 中文
        assert "深度学习" in report["markdown"]


class TestGetReport:
    """Test get_report functionality."""

    def test_get_report_returns_full_report(self, temp_db):
        """get_report returns complete report dictionary."""
        db_path, run_id = temp_db

        markdown = "# Test Report\n\n完整的报告内容。"
        template_version = "v1.0"

        report_id = store.save_report(
            db_path=db_path,
            run_id=run_id,
            markdown=markdown,
            template_version=template_version,
        )

        report = store.get_report(db_path, run_id)

        assert report is not None
        assert report["id"] == report_id
        assert report["run_id"] == run_id
        assert report["markdown"] == markdown
        assert report["template_version"] == template_version
        assert report["status"] == "draft"
        assert "created_at" in report
        assert "updated_at" in report

    def test_get_report_returns_none_when_missing(self, temp_db):
        """get_report returns None when no report exists."""
        db_path, run_id = temp_db

        report = store.get_report(db_path, run_id)

        assert report is None

    def test_get_report_handles_nonexistent_run(self, temp_db):
        """get_report returns None for nonexistent run_id."""
        db_path, _ = temp_db

        report = store.get_report(db_path, "run_nonexistent")

        assert report is None


class TestSaveClaims:
    """Test save_claims functionality."""

    def test_save_claims_batch_inserts(self, temp_db):
        """save_claims inserts multiple claims in one call."""
        db_path, run_id = temp_db

        report_id = store.save_report(
            db_path=db_path,
            run_id=run_id,
            markdown="# Report",
            template_version="v1.0",
        )

        claims = [
            {
                "claim_text": "模型在CIFAR-10上达到95%准确率",
                "claim_type": "result",
                "citation_ids": ["paper_001"],
                "evidence_ids": ["evid_001"],
                "verification_status": "supported",
                "verification_reason": "实验数据支持",
            },
            {
                "claim_text": "使用了ResNet架构",
                "claim_type": "method",
                "citation_ids": ["paper_001"],
                "evidence_ids": ["evid_002"],
                "verification_status": "supported",
                "verification_reason": "论文明确描述",
            },
            {
                "claim_text": "训练时间为72小时",
                "claim_type": "other",
                "citation_ids": [],
                "evidence_ids": [],
                "verification_status": "unverified",
                "verification_reason": "原文未明确说明",
            },
        ]

        store.save_claims(
            db_path=db_path,
            run_id=run_id,
            report_id=report_id,
            claims=claims,
        )

        # Verify claims were saved
        saved_claims = store.get_claims(db_path, run_id)
        assert len(saved_claims) == 3

    def test_save_claims_preserves_utf8_chinese(self, temp_db):
        """save_claims preserves UTF-8 Chinese in claim_text and verification_reason."""
        db_path, run_id = temp_db

        report_id = store.save_report(
            db_path=db_path,
            run_id=run_id,
            markdown="# Report",
            template_version="v1.0",
        )

        claims = [
            {
                "claim_text": "深度学习模型在图像分类任务中表现优异",
                "claim_type": "result",
                "citation_ids": ["paper_001"],
                "evidence_ids": [],
                "verification_status": "supported",
                "verification_reason": "实验数据明确支持该结论",
            }
        ]

        store.save_claims(db_path, run_id, report_id, claims)

        saved_claims = store.get_claims(db_path, run_id)
        assert len(saved_claims) == 1
        assert saved_claims[0]["claim_text"] == "深度学习模型在图像分类任务中表现优异"
        assert saved_claims[0]["verification_reason"] == "实验数据明确支持该结论"
        # Verify not escaped
        assert "深度学习" in saved_claims[0]["claim_text"]


class TestGetClaims:
    """Test get_claims functionality."""

    def test_get_claims_returns_all_claims_for_run(self, temp_db):
        """get_claims returns all claims associated with a run_id."""
        db_path, run_id = temp_db

        report_id = store.save_report(
            db_path=db_path,
            run_id=run_id,
            markdown="# Report",
            template_version="v1.0",
        )

        claims = [
            {
                "claim_text": "Claim 1",
                "claim_type": "result",
                "citation_ids": ["p1"],
                "evidence_ids": ["e1"],
                "verification_status": "supported",
                "verification_reason": "Good",
            },
            {
                "claim_text": "Claim 2",
                "claim_type": "method",
                "citation_ids": [],
                "evidence_ids": [],
                "verification_status": "unverified",
                "verification_reason": "",
            },
        ]

        store.save_claims(db_path, run_id, report_id, claims)

        saved_claims = store.get_claims(db_path, run_id)

        assert len(saved_claims) == 2
        assert all("id" in claim for claim in saved_claims)
        assert all("created_at" in claim for claim in saved_claims)
        assert saved_claims[0]["claim_text"] == "Claim 1"
        assert saved_claims[1]["claim_text"] == "Claim 2"

    def test_get_claims_returns_empty_list_when_none(self, temp_db):
        """get_claims returns empty list when no claims exist."""
        db_path, run_id = temp_db

        claims = store.get_claims(db_path, run_id)

        assert claims == []


class TestGetClaimSummary:
    """Test get_claim_summary functionality."""

    def test_get_claim_summary_aggregates_by_verification_status(self, temp_db):
        """get_claim_summary returns counts grouped by verification_status."""
        db_path, run_id = temp_db

        report_id = store.save_report(
            db_path=db_path,
            run_id=run_id,
            markdown="# Report",
            template_version="v1.0",
        )

        claims = [
            {
                "claim_text": "Supported 1",
                "claim_type": "result",
                "citation_ids": [],
                "evidence_ids": [],
                "verification_status": "supported",
                "verification_reason": "",
            },
            {
                "claim_text": "Supported 2",
                "claim_type": "result",
                "citation_ids": [],
                "evidence_ids": [],
                "verification_status": "supported",
                "verification_reason": "",
            },
            {
                "claim_text": "Weak 1",
                "claim_type": "method",
                "citation_ids": [],
                "evidence_ids": [],
                "verification_status": "weak",
                "verification_reason": "",
            },
            {
                "claim_text": "Unverified 1",
                "claim_type": "other",
                "citation_ids": [],
                "evidence_ids": [],
                "verification_status": "unverified",
                "verification_reason": "",
            },
            {
                "claim_text": "Unverified 2",
                "claim_type": "other",
                "citation_ids": [],
                "evidence_ids": [],
                "verification_status": "unverified",
                "verification_reason": "",
            },
            {
                "claim_text": "Unverified 3",
                "claim_type": "other",
                "citation_ids": [],
                "evidence_ids": [],
                "verification_status": "unverified",
                "verification_reason": "",
            },
        ]

        store.save_claims(db_path, run_id, report_id, claims)

        summary = store.get_claim_summary(db_path, run_id)

        assert summary["supported"] == 2
        assert summary["weak"] == 1
        assert summary["unverified"] == 3
        assert summary["numeric_trace_missing"] == 0
        assert summary["conflict_detected"] == 0
        assert summary["total"] == 6

    def test_get_claim_summary_returns_zeros_when_no_claims(self, temp_db):
        """get_claim_summary returns zeros for all statuses when no claims exist."""
        db_path, run_id = temp_db

        summary = store.get_claim_summary(db_path, run_id)

        assert summary["supported"] == 0
        assert summary["weak"] == 0
        assert summary["unverified"] == 0
        assert summary["numeric_trace_missing"] == 0
        assert summary["conflict_detected"] == 0
        assert summary["total"] == 0
