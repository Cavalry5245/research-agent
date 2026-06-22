"""
Tests for MVP Gate Report Script
"""

import json
import tempfile
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from app.research_pipeline.evaluation.run_mvp_gate import (
    calculate_reader_paper_count,
    calculate_time_to_report,
    check_mvp_gate,
    evaluate_single_run,
    format_markdown_report,
    generate_mvp_gate_report,
)
from app.research_pipeline.store import (
    create_candidate,
    create_paper_card,
    create_run,
    init_db,
    save_claims,
    save_report,
    update_run_status,
    update_stage,
)


@pytest.fixture
def test_db():
    """Create a temporary test database"""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name

    init_db(db_path)
    yield db_path

    # Cleanup
    Path(db_path).unlink(missing_ok=True)


@pytest.fixture
def seed_dataset_file():
    """Create a temporary seed dataset file"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False, encoding="utf-8") as f:
        # Write 3 seed questions
        for i in range(3):
            seed = {
                "question": f"Test question {i+1}",
                "gold_papers": [
                    {
                        "title": f"Paper {j+1}",
                        "doi": f"10.1234/test{j+1}",
                        "relevance": 3,
                        "reason": "Key paper",
                    }
                    for j in range(5)
                ],
                "gold_report_points": [
                    {
                        "point": f"Point {j+1}",
                        "expected_section": "method_comparison",
                    }
                    for j in range(5)
                ],
                "gold_claims": [
                    {
                        "claim": f"Claim {j+1}",
                        "paper_id": f"paper{j+1}",
                        "evidence_snippet": "Evidence text",
                    }
                    for j in range(5)
                ],
            }
            f.write(json.dumps(seed, ensure_ascii=False) + "\n")

        dataset_path = f.name

    yield dataset_path

    # Cleanup
    Path(dataset_path).unlink(missing_ok=True)


def create_mock_candidate(paper_id: str):
    """Create a mock PaperCandidate object"""
    from app.research_pipeline.schemas import PaperCandidate

    return PaperCandidate(
        paper_id=paper_id,
        source="semantic_scholar",
        title=f"Test Paper {paper_id}",
        authors=["Author A", "Author B"],
        year=2024,
        venue="Test Conference",
        abstract="Test abstract",
        doi=f"10.1234/{paper_id}",
        arxiv_id=None,
        semantic_scholar_id=None,
        zotero_item_id=None,
        url=f"https://example.com/{paper_id}",
        pdf_url=None,
        local_pdf_path=None,
        citation_count=100,
        relevance_score=0.95,
        metadata={},
    )


def create_mock_paper_card(paper_id: str, status: str = "completed"):
    """Create a mock PaperCard object"""
    from app.research_pipeline.schemas import PaperCard

    return PaperCard(
        paper_id=paper_id,
        status=status,
        extraction_mode="abstract_only",
        title=f"Test Paper {paper_id}",
        bibliographic_metadata={"authors": ["Author A"], "year": 2024},
        research_problem="Test problem",
        method="Test method",
        datasets=["Dataset1"],
        metrics=["Metric1"],
        key_results=["Result1"],
        limitations=["Limitation1"],
        assumptions=["Assumption1"],
        future_work=["Future1"],
        claims=[
            {"claim": "Claim1", "type": "numeric"},
            {"claim": "Claim2", "type": "qualitative"},
        ],
        evidence=[],
        error=None,
    )


def create_completed_run(test_db: str, duration_seconds: float = 120.0, paper_count: int = 5) -> str:
    """Helper to create a completed run with timing and paper cards"""
    # Create run
    run_id = create_run(
        db_path=test_db,
        question="Test question",
        source_mode="web_search",
        max_reader_papers=10,
        reader_concurrency=3,
    )

    # Set started_at timestamp
    started_at = datetime.utcnow() - timedelta(seconds=duration_seconds)
    import sqlite3
    conn = sqlite3.connect(test_db)
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE research_runs SET started_at = ?, status = 'running' WHERE id = ?",
        (started_at.isoformat(), run_id),
    )
    conn.commit()
    conn.close()

    # Create candidates and paper cards
    for i in range(paper_count):
        candidate = create_mock_candidate(f"paper{i+1}")
        candidate_id = create_candidate(test_db, run_id, candidate)

        paper_card = create_mock_paper_card(f"paper{i+1}")
        create_paper_card(test_db, run_id, paper_card)

    # Complete all stages
    stages = ["planner", "retriever", "reader", "synthesis", "harness"]
    for stage in stages:
        update_stage(test_db, run_id, stage, "completed", progress=1.0, message="Done")

    # Mark run as completed
    update_run_status(test_db, run_id, "completed")

    # Create report
    report_id = save_report(
        db_path=test_db,
        run_id=run_id,
        markdown="# Test Report\n\nThis is a test report.",
        template_version="1.0",
    )

    # Create claims with verification status
    claims = [
        {
            "claim_text": f"Test claim {i+1}",
            "claim_type": "numeric",
            "citation_ids": ["paper1"],
            "evidence_ids": [],
            "verification_status": "supported" if i % 2 == 0 else "weak",
            "verification_reason": "Test reason",
        }
        for i in range(10)
    ]
    save_claims(test_db, run_id, report_id, claims)

    return run_id


class TestCalculateTimeToReport:
    """Test calculate_time_to_report function"""

    def test_valid_timing(self):
        """Test valid start and end times"""
        started = datetime(2024, 1, 1, 12, 0, 0)
        completed = datetime(2024, 1, 1, 12, 5, 30)

        run_detail = {
            "started_at": started.isoformat(),
            "completed_at": completed.isoformat(),
        }

        time_seconds = calculate_time_to_report(run_detail)
        assert time_seconds == 330.0  # 5 minutes 30 seconds

    def test_missing_started_at(self):
        """Test missing started_at returns None"""
        run_detail = {
            "completed_at": datetime.utcnow().isoformat(),
        }
        assert calculate_time_to_report(run_detail) is None

    def test_missing_completed_at(self):
        """Test missing completed_at returns None"""
        run_detail = {
            "started_at": datetime.utcnow().isoformat(),
        }
        assert calculate_time_to_report(run_detail) is None

    def test_none_run_detail(self):
        """Test None run_detail returns None"""
        assert calculate_time_to_report(None) is None

    def test_invalid_datetime_format(self):
        """Test invalid datetime format returns None"""
        run_detail = {
            "started_at": "not a datetime",
            "completed_at": "also not a datetime",
        }
        assert calculate_time_to_report(run_detail) is None


class TestCalculateReaderPaperCount:
    """Test calculate_reader_paper_count function"""

    def test_with_cards(self):
        """Test counting paper cards"""
        run_detail = {
            "cards": [
                {"paper_id": "paper1"},
                {"paper_id": "paper2"},
                {"paper_id": "paper3"},
            ]
        }
        assert calculate_reader_paper_count(run_detail) == 3

    def test_empty_cards(self):
        """Test empty cards list"""
        run_detail = {"cards": []}
        assert calculate_reader_paper_count(run_detail) == 0

    def test_missing_cards_key(self):
        """Test missing cards key returns 0"""
        run_detail = {}
        assert calculate_reader_paper_count(run_detail) == 0

    def test_none_run_detail(self):
        """Test None run_detail returns 0"""
        assert calculate_reader_paper_count(None) == 0


class TestCheckMvpGate:
    """Test check_mvp_gate function"""

    def test_all_conditions_pass(self):
        """Test all MVP gate conditions passing"""
        run_results = [
            {
                "run_id": "run1",
                "status": "completed",
                "completion_rate": 1.0,
                "time_to_report": 200.0,
                "reader_paper_count": 5,
                "claim_verification_coverage": 0.8,
                "total_claims": 10,
            },
            {
                "run_id": "run2",
                "status": "completed",
                "completion_rate": 1.0,
                "time_to_report": 250.0,
                "reader_paper_count": 4,
                "claim_verification_coverage": 0.7,
                "total_claims": 8,
            },
            {
                "run_id": "run3",
                "status": "completed",
                "completion_rate": 1.0,
                "time_to_report": 180.0,
                "reader_paper_count": 3,
                "claim_verification_coverage": 0.9,
                "total_claims": 12,
            },
        ]

        gate_result = check_mvp_gate(run_results)

        assert gate_result["passed"] is True
        assert gate_result["conditions"]["completion"]["passed"] is True
        assert gate_result["conditions"]["time_to_report"]["passed"] is True
        assert gate_result["conditions"]["reader_paper_count"]["passed"] is True
        assert gate_result["conditions"]["claim_verification_coverage"]["passed"] is True

    def test_completion_fails(self):
        """Test completion rate below threshold"""
        run_results = [
            {
                "run_id": "run1",
                "status": "completed",
                "completion_rate": 1.0,
                "time_to_report": 200.0,
                "reader_paper_count": 5,
                "claim_verification_coverage": 0.8,
                "total_claims": 10,
            },
            {
                "run_id": "run2",
                "status": "failed",
                "completion_rate": 0.0,
                "time_to_report": None,
                "reader_paper_count": 2,
                "claim_verification_coverage": None,
                "total_claims": 0,
            },
            {
                "run_id": "run3",
                "status": "failed",
                "completion_rate": 0.0,
                "time_to_report": None,
                "reader_paper_count": 1,
                "claim_verification_coverage": None,
                "total_claims": 0,
            },
        ]

        gate_result = check_mvp_gate(run_results)

        assert gate_result["passed"] is False
        assert gate_result["conditions"]["completion"]["passed"] is False
        assert "Completion rate below threshold" in gate_result["reason"]

    def test_time_to_report_fails(self):
        """Test time to report above threshold"""
        run_results = [
            {
                "run_id": "run1",
                "status": "completed",
                "completion_rate": 1.0,
                "time_to_report": 350.0,  # Too slow
                "reader_paper_count": 5,
                "claim_verification_coverage": 0.8,
                "total_claims": 10,
            },
            {
                "run_id": "run2",
                "status": "completed",
                "completion_rate": 1.0,
                "time_to_report": 400.0,  # Too slow
                "reader_paper_count": 4,
                "claim_verification_coverage": 0.7,
                "total_claims": 8,
            },
            {
                "run_id": "run3",
                "status": "completed",
                "completion_rate": 1.0,
                "time_to_report": 380.0,  # Too slow
                "reader_paper_count": 3,
                "claim_verification_coverage": 0.9,
                "total_claims": 12,
            },
        ]

        gate_result = check_mvp_gate(run_results)

        assert gate_result["passed"] is False
        assert gate_result["conditions"]["time_to_report"]["passed"] is False
        assert "Time to report too slow" in gate_result["reason"]

    def test_reader_paper_count_fails(self):
        """Test reader paper count below threshold"""
        run_results = [
            {
                "run_id": "run1",
                "status": "completed",
                "completion_rate": 1.0,
                "time_to_report": 200.0,
                "reader_paper_count": 2,  # Too few
                "claim_verification_coverage": 0.8,
                "total_claims": 10,
            },
            {
                "run_id": "run2",
                "status": "completed",
                "completion_rate": 1.0,
                "time_to_report": 250.0,
                "reader_paper_count": 1,  # Too few
                "claim_verification_coverage": 0.7,
                "total_claims": 8,
            },
            {
                "run_id": "run3",
                "status": "completed",
                "completion_rate": 1.0,
                "time_to_report": 180.0,
                "reader_paper_count": 2,  # Too few
                "claim_verification_coverage": 0.9,
                "total_claims": 12,
            },
        ]

        gate_result = check_mvp_gate(run_results)

        assert gate_result["passed"] is False
        assert gate_result["conditions"]["reader_paper_count"]["passed"] is False
        assert "Reader paper count below threshold" in gate_result["reason"]

    def test_claim_verification_coverage_fails(self):
        """Test claim verification coverage below threshold"""
        run_results = [
            {
                "run_id": "run1",
                "status": "completed",
                "completion_rate": 1.0,
                "time_to_report": 200.0,
                "reader_paper_count": 5,
                "claim_verification_coverage": 0.5,  # Too low
                "total_claims": 10,
            },
            {
                "run_id": "run2",
                "status": "completed",
                "completion_rate": 1.0,
                "time_to_report": 250.0,
                "reader_paper_count": 4,
                "claim_verification_coverage": 0.4,  # Too low
                "total_claims": 8,
            },
            {
                "run_id": "run3",
                "status": "completed",
                "completion_rate": 1.0,
                "time_to_report": 180.0,
                "reader_paper_count": 3,
                "claim_verification_coverage": 0.3,  # Too low
                "total_claims": 12,
            },
        ]

        gate_result = check_mvp_gate(run_results)

        assert gate_result["passed"] is False
        assert gate_result["conditions"]["claim_verification_coverage"]["passed"] is False
        assert "Claim verification coverage below threshold" in gate_result["reason"]

    def test_empty_run_results(self):
        """Test empty run results"""
        gate_result = check_mvp_gate([])

        assert gate_result["passed"] is False
        assert "No runs to evaluate" in gate_result["reason"]

    def test_two_thirds_threshold(self):
        """Test 2/3 completion threshold"""
        # With 3 runs, need 2 completed
        run_results = [
            {"run_id": "run1", "status": "completed", "completion_rate": 1.0,
             "time_to_report": 200.0, "reader_paper_count": 5,
             "claim_verification_coverage": 0.8, "total_claims": 10},
            {"run_id": "run2", "status": "completed", "completion_rate": 1.0,
             "time_to_report": 250.0, "reader_paper_count": 4,
             "claim_verification_coverage": 0.7, "total_claims": 8},
            {"run_id": "run3", "status": "failed", "completion_rate": 0.0,
             "time_to_report": None, "reader_paper_count": 1,
             "claim_verification_coverage": None, "total_claims": 0},
        ]

        gate_result = check_mvp_gate(run_results)
        assert gate_result["conditions"]["completion"]["passed"] is True


class TestEvaluateSingleRun:
    """Test evaluate_single_run function"""

    def test_evaluate_completed_run(self, test_db):
        """Test evaluating a completed run"""
        run_id = create_completed_run(test_db, duration_seconds=180.0, paper_count=5)

        result = evaluate_single_run(test_db, run_id)

        assert result["run_id"] == run_id
        assert result["status"] == "completed"
        assert result["completion_rate"] == 1.0
        assert result["time_to_report"] == pytest.approx(180.0, abs=1.0)
        assert result["reader_paper_count"] == 5
        assert result["claim_verification_coverage"] is not None
        assert result["total_claims"] == 10

    def test_evaluate_failed_run(self, test_db):
        """Test evaluating a failed run"""
        run_id = create_run(
            db_path=test_db,
            question="Test question",
            source_mode="web_search",
            max_reader_papers=10,
            reader_concurrency=3,
        )

        update_run_status(test_db, run_id, "failed", error="Test error")

        result = evaluate_single_run(test_db, run_id)

        assert result["run_id"] == run_id
        assert result["status"] == "failed"
        assert result["completion_rate"] == 0.0
        assert result["time_to_report"] is None
        assert result["reader_paper_count"] == 0
        assert result["claim_verification_coverage"] is None


class TestGenerateMvpGateReport:
    """Test generate_mvp_gate_report function"""

    def test_generate_report_all_passing(self, test_db, seed_dataset_file):
        """Test generating report with all conditions passing"""
        # Create 3 completed runs
        run_ids = [
            create_completed_run(test_db, duration_seconds=180.0, paper_count=5),
            create_completed_run(test_db, duration_seconds=220.0, paper_count=4),
            create_completed_run(test_db, duration_seconds=200.0, paper_count=6),
        ]

        with tempfile.TemporaryDirectory() as tmpdir:
            json_path = Path(tmpdir) / "report.json"
            md_path = Path(tmpdir) / "report.md"

            report = generate_mvp_gate_report(
                db_path=test_db,
                run_ids=run_ids,
                seed_dataset_path=seed_dataset_file,
                output_json_path=str(json_path),
                output_md_path=str(md_path),
            )

            # Check report structure
            assert report["gate_status"] == "PASSED"
            assert report["total_runs"] == 3
            assert report["seed_questions"] == 3
            assert report["gate_check"]["passed"] is True
            assert len(report["run_results"]) == 3

            # Check files were created
            assert json_path.exists()
            assert md_path.exists()

            # Check JSON content
            with json_path.open("r", encoding="utf-8") as f:
                json_report = json.load(f)
                assert json_report["gate_status"] == "PASSED"

            # Check Markdown content
            with md_path.open("r", encoding="utf-8") as f:
                md_content = f.read()
                assert "✅ PASSED" in md_content
                assert "MVP Gate Conditions" in md_content

    def test_generate_report_failing(self, test_db):
        """Test generating report with failing conditions"""
        # Create 1 completed and 2 failed runs
        run_id1 = create_completed_run(test_db, duration_seconds=180.0, paper_count=5)
        run_id2 = create_run(test_db, "Test 2", "web_search", 10, 3)
        run_id3 = create_run(test_db, "Test 3", "web_search", 10, 3)

        update_run_status(test_db, run_id2, "failed")
        update_run_status(test_db, run_id3, "failed")

        report = generate_mvp_gate_report(
            db_path=test_db,
            run_ids=[run_id1, run_id2, run_id3],
        )

        assert report["gate_status"] == "FAILED"
        assert report["gate_check"]["passed"] is False
        assert "Completion rate below threshold" in report["gate_check"]["reason"]

    def test_generate_report_without_seed_dataset(self, test_db):
        """Test generating report without seed dataset"""
        run_ids = [
            create_completed_run(test_db, duration_seconds=180.0, paper_count=5),
        ]

        report = generate_mvp_gate_report(
            db_path=test_db,
            run_ids=run_ids,
        )

        assert report["seed_questions"] is None
        assert "total_runs" in report


class TestFormatMarkdownReport:
    """Test format_markdown_report function"""

    def test_format_passing_report(self):
        """Test formatting a passing report"""
        report = {
            "generated_at": "2024-01-01T12:00:00",
            "total_runs": 3,
            "seed_questions": 3,
            "gate_status": "PASSED",
            "gate_check": {
                "passed": True,
                "reason": "All conditions passed",
                "conditions": {
                    "completion": {
                        "passed": True,
                        "value": "3/3",
                        "threshold": "≥2/3",
                        "detail": "3 out of 3 runs completed",
                    },
                    "time_to_report": {
                        "passed": True,
                        "value": "200.0s",
                        "threshold": "<300s",
                        "detail": "Median time: 200.0s",
                    },
                    "reader_paper_count": {
                        "passed": True,
                        "value": "5",
                        "threshold": "≥3",
                        "detail": "Median papers read: 5",
                    },
                    "claim_verification_coverage": {
                        "passed": True,
                        "value": "80.0%",
                        "threshold": "≥60%",
                        "detail": "Mean coverage: 80.0%",
                    },
                },
            },
            "run_results": [
                {
                    "run_id": "run1",
                    "status": "completed",
                    "time_to_report": 200.0,
                    "reader_paper_count": 5,
                    "total_claims": 10,
                    "claim_verification_coverage": 0.8,
                },
            ],
        }

        md_content = format_markdown_report(report)

        assert "# Research Pipeline MVP Gate Report" in md_content
        assert "✅ PASSED" in md_content
        assert "MVP Gate Conditions" in md_content
        assert "Completion" in md_content
        assert "Time To Report" in md_content
        assert "Reader Paper Count" in md_content
        assert "Claim Verification Coverage" in md_content
        assert "Run Results Summary" in md_content
        assert "run1" in md_content

    def test_format_failing_report(self):
        """Test formatting a failing report"""
        report = {
            "generated_at": "2024-01-01T12:00:00",
            "total_runs": 3,
            "seed_questions": 3,
            "gate_status": "FAILED",
            "gate_check": {
                "passed": False,
                "reason": "Completion rate below threshold: 1/3 < 2",
                "conditions": {
                    "completion": {
                        "passed": False,
                        "value": "1/3",
                        "threshold": "≥2/3",
                        "detail": "1 out of 3 runs completed",
                    },
                    "time_to_report": {
                        "passed": True,
                        "value": "200.0s",
                        "threshold": "<300s",
                        "detail": "Median time: 200.0s",
                    },
                    "reader_paper_count": {
                        "passed": True,
                        "value": "5",
                        "threshold": "≥3",
                        "detail": "Median papers read: 5",
                    },
                    "claim_verification_coverage": {
                        "passed": True,
                        "value": "80.0%",
                        "threshold": "≥60%",
                        "detail": "Mean coverage: 80.0%",
                    },
                },
            },
            "run_results": [],
        }

        md_content = format_markdown_report(report)

        assert "❌ FAILED" in md_content
        assert "Failure Reasons" in md_content
        assert "Completion rate below threshold" in md_content
