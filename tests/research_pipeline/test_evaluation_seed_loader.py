"""
Tests for Seed Evaluation Dataset Loader
"""

import json
import tempfile
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.research_pipeline.evaluation.seed_loader import (
    GoldClaim,
    GoldPaper,
    GoldReportPoint,
    SeedDataset,
    SeedQuestion,
    load_seed_dataset,
)


class TestGoldPaper:
    """Test GoldPaper schema validation"""

    def test_valid_gold_paper_with_all_ids(self):
        """Test valid paper with all identifiers"""
        paper = GoldPaper(
            title="Test Paper",
            doi="10.1234/test",
            arxiv_id="1234.5678",
            semantic_scholar_id="abc123",
            relevance=3,
            reason="Key foundational work",
        )
        assert paper.title == "Test Paper"
        assert paper.relevance == 3

    def test_valid_gold_paper_with_doi_only(self):
        """Test valid paper with DOI only"""
        paper = GoldPaper(
            title="Test Paper", doi="10.1234/test", relevance=2, reason="Important work"
        )
        assert paper.doi == "10.1234/test"
        assert paper.arxiv_id is None

    def test_valid_gold_paper_with_arxiv_only(self):
        """Test valid paper with arXiv ID only"""
        paper = GoldPaper(
            title="Test Paper",
            arxiv_id="1234.5678",
            relevance=1,
            reason="Relevant paper",
        )
        assert paper.arxiv_id == "1234.5678"
        assert paper.doi is None

    def test_invalid_relevance_too_low(self):
        """Test relevance score below 1"""
        with pytest.raises(ValidationError, match="greater than or equal to 1"):
            GoldPaper(
                title="Test Paper",
                doi="10.1234/test",
                relevance=0,
                reason="Test",
            )

    def test_invalid_relevance_too_high(self):
        """Test relevance score above 3"""
        with pytest.raises(ValidationError, match="less than or equal to 3"):
            GoldPaper(
                title="Test Paper",
                doi="10.1234/test",
                relevance=4,
                reason="Test",
            )

    def test_missing_all_identifiers(self):
        """Test paper with no identifiers fails validation"""
        with pytest.raises(
            ValueError,
            match="At least one of doi, arxiv_id, or semantic_scholar_id must be provided",
        ):
            GoldPaper(title="Test Paper", relevance=2, reason="Test")


class TestGoldReportPoint:
    """Test GoldReportPoint schema validation"""

    def test_valid_report_point(self):
        """Test valid report point"""
        point = GoldReportPoint(
            point="This is a key finding",
            expected_section="method_comparison",
            required_papers=["1234.5678", "8765.4321"],
        )
        assert point.point == "This is a key finding"
        assert point.expected_section == "method_comparison"
        assert len(point.required_papers) == 2

    def test_valid_report_point_with_empty_papers(self):
        """Test report point with empty required_papers"""
        point = GoldReportPoint(
            point="General observation", expected_section="results"
        )
        assert point.required_papers == []

    def test_invalid_section(self):
        """Test invalid expected_section value"""
        with pytest.raises(ValueError, match="expected_section must be one of"):
            GoldReportPoint(
                point="Test point",
                expected_section="invalid_section",
                required_papers=["1234.5678"],
            )

    def test_valid_sections(self):
        """Test all valid section values"""
        valid_sections = [
            "method_comparison",
            "dataset_metrics",
            "gap",
            "limitation",
            "background",
            "results",
            "future_work",
        ]
        for section in valid_sections:
            point = GoldReportPoint(
                point="Test point", expected_section=section, required_papers=[]
            )
            assert point.expected_section == section


class TestGoldClaim:
    """Test GoldClaim schema validation"""

    def test_valid_claim_with_all_fields(self):
        """Test valid claim with all fields"""
        claim = GoldClaim(
            claim="The model achieves 95% accuracy",
            paper_id="1234.5678",
            evidence_snippet="Our model achieves 95% accuracy on the test set",
            page=7,
            section="Results",
            numeric=True,
        )
        assert claim.numeric is True
        assert claim.page == 7

    def test_valid_claim_with_optional_fields_none(self):
        """Test valid claim with optional fields as None"""
        claim = GoldClaim(
            claim="The approach is novel",
            paper_id="1234.5678",
            evidence_snippet="We propose a novel approach",
        )
        assert claim.page is None
        assert claim.section is None
        assert claim.numeric is False


class TestSeedQuestion:
    """Test SeedQuestion schema validation"""

    def test_valid_seed_question(self):
        """Test valid seed question with minimum required items"""
        question = SeedQuestion(
            question="What is the state of the art?",
            gold_papers=[
                GoldPaper(
                    title=f"Paper {i}",
                    doi=f"10.1234/{i}",
                    relevance=3,
                    reason="Test",
                )
                for i in range(5)
            ],
            gold_report_points=[
                GoldReportPoint(
                    point=f"Point {i}", expected_section="results", required_papers=[]
                )
                for i in range(5)
            ],
            gold_claims=[
                GoldClaim(
                    claim=f"Claim {i}",
                    paper_id=f"paper_{i}",
                    evidence_snippet=f"Evidence {i}",
                )
                for i in range(5)
            ],
        )
        assert len(question.gold_papers) == 5
        assert len(question.gold_report_points) == 5
        assert len(question.gold_claims) == 5

    def test_empty_question(self):
        """Test empty question string"""
        with pytest.raises(ValueError, match="question cannot be empty"):
            SeedQuestion(
                question="",
                gold_papers=[
                    GoldPaper(
                        title=f"Paper {i}",
                        doi=f"10.1234/{i}",
                        relevance=3,
                        reason="Test",
                    )
                    for i in range(5)
                ],
                gold_report_points=[
                    GoldReportPoint(
                        point=f"Point {i}",
                        expected_section="results",
                        required_papers=[],
                    )
                    for i in range(5)
                ],
                gold_claims=[
                    GoldClaim(
                        claim=f"Claim {i}",
                        paper_id=f"paper_{i}",
                        evidence_snippet=f"Evidence {i}",
                    )
                    for i in range(5)
                ],
            )

    def test_whitespace_question(self):
        """Test whitespace-only question"""
        with pytest.raises(ValueError, match="question cannot be empty"):
            SeedQuestion(
                question="   ",
                gold_papers=[
                    GoldPaper(
                        title=f"Paper {i}",
                        doi=f"10.1234/{i}",
                        relevance=3,
                        reason="Test",
                    )
                    for i in range(5)
                ],
                gold_report_points=[
                    GoldReportPoint(
                        point=f"Point {i}",
                        expected_section="results",
                        required_papers=[],
                    )
                    for i in range(5)
                ],
                gold_claims=[
                    GoldClaim(
                        claim=f"Claim {i}",
                        paper_id=f"paper_{i}",
                        evidence_snippet=f"Evidence {i}",
                    )
                    for i in range(5)
                ],
            )

    def test_too_few_gold_papers(self):
        """Test fewer than 5 gold papers"""
        with pytest.raises(ValueError):
            SeedQuestion(
                question="What is the state of the art?",
                gold_papers=[
                    GoldPaper(
                        title=f"Paper {i}",
                        doi=f"10.1234/{i}",
                        relevance=3,
                        reason="Test",
                    )
                    for i in range(4)
                ],
                gold_report_points=[
                    GoldReportPoint(
                        point=f"Point {i}",
                        expected_section="results",
                        required_papers=[],
                    )
                    for i in range(5)
                ],
                gold_claims=[
                    GoldClaim(
                        claim=f"Claim {i}",
                        paper_id=f"paper_{i}",
                        evidence_snippet=f"Evidence {i}",
                    )
                    for i in range(5)
                ],
            )

    def test_too_few_gold_report_points(self):
        """Test fewer than 5 gold report points"""
        with pytest.raises(ValueError):
            SeedQuestion(
                question="What is the state of the art?",
                gold_papers=[
                    GoldPaper(
                        title=f"Paper {i}",
                        doi=f"10.1234/{i}",
                        relevance=3,
                        reason="Test",
                    )
                    for i in range(5)
                ],
                gold_report_points=[
                    GoldReportPoint(
                        point=f"Point {i}",
                        expected_section="results",
                        required_papers=[],
                    )
                    for i in range(3)
                ],
                gold_claims=[
                    GoldClaim(
                        claim=f"Claim {i}",
                        paper_id=f"paper_{i}",
                        evidence_snippet=f"Evidence {i}",
                    )
                    for i in range(5)
                ],
            )

    def test_too_few_gold_claims(self):
        """Test fewer than 5 gold claims"""
        with pytest.raises(ValueError):
            SeedQuestion(
                question="What is the state of the art?",
                gold_papers=[
                    GoldPaper(
                        title=f"Paper {i}",
                        doi=f"10.1234/{i}",
                        relevance=3,
                        reason="Test",
                    )
                    for i in range(5)
                ],
                gold_report_points=[
                    GoldReportPoint(
                        point=f"Point {i}",
                        expected_section="results",
                        required_papers=[],
                    )
                    for i in range(5)
                ],
                gold_claims=[
                    GoldClaim(
                        claim=f"Claim {i}",
                        paper_id=f"paper_{i}",
                        evidence_snippet=f"Evidence {i}",
                    )
                    for i in range(2)
                ],
            )


class TestLoadSeedDataset:
    """Test load_seed_dataset function"""

    def test_load_valid_dataset(self):
        """Test loading valid dataset from JSONL"""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".jsonl", delete=False, encoding="utf-8"
        ) as f:
            for i in range(3):
                data = {
                    "question": f"Question {i}",
                    "gold_papers": [
                        {
                            "title": f"Paper {j}",
                            "doi": f"10.1234/{j}",
                            "relevance": 3,
                            "reason": "Test",
                        }
                        for j in range(5)
                    ],
                    "gold_report_points": [
                        {
                            "point": f"Point {j}",
                            "expected_section": "results",
                            "required_papers": [],
                        }
                        for j in range(5)
                    ],
                    "gold_claims": [
                        {
                            "claim": f"Claim {j}",
                            "paper_id": f"paper_{j}",
                            "evidence_snippet": f"Evidence {j}",
                        }
                        for j in range(5)
                    ],
                }
                f.write(json.dumps(data) + "\n")
            temp_path = f.name

        try:
            dataset = load_seed_dataset(temp_path)
            assert len(dataset.questions) == 3
            assert all(len(q.gold_papers) == 5 for q in dataset.questions)
            assert all(len(q.gold_report_points) == 5 for q in dataset.questions)
            assert all(len(q.gold_claims) == 5 for q in dataset.questions)
        finally:
            Path(temp_path).unlink()

    def test_load_dataset_file_not_found(self):
        """Test loading non-existent file"""
        with pytest.raises(FileNotFoundError, match="Dataset file not found"):
            load_seed_dataset("/nonexistent/path.jsonl")

    def test_load_dataset_invalid_json(self):
        """Test loading file with invalid JSON"""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".jsonl", delete=False, encoding="utf-8"
        ) as f:
            f.write("not valid json\n")
            temp_path = f.name

        try:
            with pytest.raises(json.JSONDecodeError, match="Invalid JSON at line 1"):
                load_seed_dataset(temp_path)
        finally:
            Path(temp_path).unlink()

    def test_load_dataset_validation_error(self):
        """Test loading file with validation errors"""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".jsonl", delete=False, encoding="utf-8"
        ) as f:
            data = {
                "question": "Test question",
                "gold_papers": [],  # Empty - should fail
                "gold_report_points": [],
                "gold_claims": [],
            }
            f.write(json.dumps(data) + "\n")
            temp_path = f.name

        try:
            with pytest.raises(ValueError, match="Validation error at line 1"):
                load_seed_dataset(temp_path)
        finally:
            Path(temp_path).unlink()

    def test_load_dataset_too_few_questions(self):
        """Test loading dataset with fewer than 3 questions"""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".jsonl", delete=False, encoding="utf-8"
        ) as f:
            for i in range(2):
                data = {
                    "question": f"Question {i}",
                    "gold_papers": [
                        {
                            "title": f"Paper {j}",
                            "doi": f"10.1234/{j}",
                            "relevance": 3,
                            "reason": "Test",
                        }
                        for j in range(5)
                    ],
                    "gold_report_points": [
                        {
                            "point": f"Point {j}",
                            "expected_section": "results",
                            "required_papers": [],
                        }
                        for j in range(5)
                    ],
                    "gold_claims": [
                        {
                            "claim": f"Claim {j}",
                            "paper_id": f"paper_{j}",
                            "evidence_snippet": f"Evidence {j}",
                        }
                        for j in range(5)
                    ],
                }
                f.write(json.dumps(data) + "\n")
            temp_path = f.name

        try:
            with pytest.raises(
                ValueError, match="Dataset must contain at least 3 questions"
            ):
                load_seed_dataset(temp_path)
        finally:
            Path(temp_path).unlink()

    def test_load_dataset_with_empty_lines(self):
        """Test loading dataset with empty lines (should be ignored)"""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".jsonl", delete=False, encoding="utf-8"
        ) as f:
            for i in range(3):
                data = {
                    "question": f"Question {i}",
                    "gold_papers": [
                        {
                            "title": f"Paper {j}",
                            "doi": f"10.1234/{j}",
                            "relevance": 3,
                            "reason": "Test",
                        }
                        for j in range(5)
                    ],
                    "gold_report_points": [
                        {
                            "point": f"Point {j}",
                            "expected_section": "results",
                            "required_papers": [],
                        }
                        for j in range(5)
                    ],
                    "gold_claims": [
                        {
                            "claim": f"Claim {j}",
                            "paper_id": f"paper_{j}",
                            "evidence_snippet": f"Evidence {j}",
                        }
                        for j in range(5)
                    ],
                }
                f.write(json.dumps(data) + "\n")
                f.write("\n")  # Empty line
            temp_path = f.name

        try:
            dataset = load_seed_dataset(temp_path)
            assert len(dataset.questions) == 3
        finally:
            Path(temp_path).unlink()

    def test_load_actual_seed_dataset(self):
        """Test loading the actual seed dataset file"""
        dataset_path = Path("app/evaluation/datasets/research_pipeline_seed.jsonl")
        if not dataset_path.exists():
            pytest.skip("Seed dataset file does not exist")

        dataset = load_seed_dataset(dataset_path)
        assert len(dataset.questions) >= 3
        for question in dataset.questions:
            assert len(question.gold_papers) >= 5
            assert len(question.gold_report_points) >= 5
            assert len(question.gold_claims) >= 5
            assert question.question.strip()


class TestSeedDataset:
    """Test SeedDataset schema validation"""

    def test_valid_seed_dataset(self):
        """Test valid seed dataset with 3 questions"""
        questions = [
            SeedQuestion(
                question=f"Question {i}",
                gold_papers=[
                    GoldPaper(
                        title=f"Paper {j}",
                        doi=f"10.1234/{j}",
                        relevance=3,
                        reason="Test",
                    )
                    for j in range(5)
                ],
                gold_report_points=[
                    GoldReportPoint(
                        point=f"Point {j}",
                        expected_section="results",
                        required_papers=[],
                    )
                    for j in range(5)
                ],
                gold_claims=[
                    GoldClaim(
                        claim=f"Claim {j}",
                        paper_id=f"paper_{j}",
                        evidence_snippet=f"Evidence {j}",
                    )
                    for j in range(5)
                ],
            )
            for i in range(3)
        ]
        dataset = SeedDataset(questions=questions)
        assert len(dataset.questions) == 3

    def test_dataset_too_few_questions(self):
        """Test dataset with fewer than 3 questions"""
        questions = [
            SeedQuestion(
                question=f"Question {i}",
                gold_papers=[
                    GoldPaper(
                        title=f"Paper {j}",
                        doi=f"10.1234/{j}",
                        relevance=3,
                        reason="Test",
                    )
                    for j in range(5)
                ],
                gold_report_points=[
                    GoldReportPoint(
                        point=f"Point {j}",
                        expected_section="results",
                        required_papers=[],
                    )
                    for j in range(5)
                ],
                gold_claims=[
                    GoldClaim(
                        claim=f"Claim {j}",
                        paper_id=f"paper_{j}",
                        evidence_snippet=f"Evidence {j}",
                    )
                    for j in range(5)
                ],
            )
            for i in range(2)
        ]
        with pytest.raises(ValueError):
            SeedDataset(questions=questions)
