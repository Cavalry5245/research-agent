"""
Tests for Research Pipeline Schemas

测试 research_pipeline 的核心 Pydantic schema。
"""

import pytest
from datetime import datetime
from pydantic import ValidationError

from app.research_pipeline.schemas import (
    # Enums and literals
    SourceMode,
    RunStatus,
    StageStatus,
    StageName,
    VerificationStatus,
    ClaimType,
    ExtractionMode,
    # Request schemas
    ResearchRunCreateRequest,
    # Response schemas
    ResearchRunCreateResponse,
    ResearchRunListResponse,
    ResearchRunSummary,
    ResearchRunDetailResponse,
    # Core data models
    PaperCandidate,
    PaperCard,
    ReportClaim,
    ResearchPlan,
    ResearchStage,
    ResearchEvent,
    ResearchReport,
)


class TestSourceMode:
    """测试 SourceMode literal"""

    def test_source_mode_values(self):
        """验证 source_mode 包含三种模式"""
        assert SourceMode.__args__ == ("web_search", "zotero_only", "hybrid")


class TestRunStatus:
    """测试 RunStatus literal"""

    def test_run_status_values(self):
        """验证 run status 包含六种状态"""
        assert RunStatus.__args__ == (
            "queued",
            "running",
            "completed",
            "failed",
            "cancelled",
            "degraded",
        )


class TestStageStatus:
    """测试 StageStatus literal"""

    def test_stage_status_values(self):
        """验证 stage status 包含五种状态"""
        assert StageStatus.__args__ == (
            "queued",
            "running",
            "completed",
            "failed",
            "degraded",
        )


class TestStageName:
    """测试 StageName literal"""

    def test_stage_name_values(self):
        """验证 stage name 包含五个阶段"""
        assert StageName.__args__ == (
            "planner",
            "retriever",
            "reader",
            "synthesis",
            "harness",
        )


class TestVerificationStatus:
    """测试 VerificationStatus literal"""

    def test_verification_status_values(self):
        """验证 verification_status 包含 PRD 要求的五种状态"""
        assert VerificationStatus.__args__ == (
            "supported",
            "weak",
            "unverified",
            "numeric_trace_missing",
            "conflict_detected",
        )


class TestResearchRunCreateRequest:
    """测试 ResearchRunCreateRequest schema"""

    def test_minimal_request(self):
        """测试最小必填字段"""
        req = ResearchRunCreateRequest(question="What is RAG?")
        assert req.question == "What is RAG?"
        assert req.source_mode == "hybrid"  # 默认值
        assert req.max_reader_papers == 8  # 默认值
        assert req.reader_concurrency == 3  # 默认值

    def test_all_fields(self):
        """测试所有字段"""
        req = ResearchRunCreateRequest(
            question="What is RAG evaluation?",
            source_mode="web_search",
            zotero_collection_key="ABC123",
            max_reader_papers=10,
            reader_concurrency=5,
            year_start=2020,
            year_end=2025,
            venue_filter=["ACL", "EMNLP"],
            keywords=["RAG", "evaluation"],
        )
        assert req.question == "What is RAG evaluation?"
        assert req.source_mode == "web_search"
        assert req.zotero_collection_key == "ABC123"
        assert req.max_reader_papers == 10
        assert req.reader_concurrency == 5
        assert req.year_start == 2020
        assert req.year_end == 2025
        assert req.venue_filter == ["ACL", "EMNLP"]
        assert req.keywords == ["RAG", "evaluation"]

    def test_max_reader_papers_validation_min(self):
        """测试 max_reader_papers 最小值验证"""
        with pytest.raises(ValidationError) as exc_info:
            ResearchRunCreateRequest(question="Test", max_reader_papers=2)
        assert "max_reader_papers" in str(exc_info.value)

    def test_max_reader_papers_validation_max(self):
        """测试 max_reader_papers 最大值验证"""
        with pytest.raises(ValidationError) as exc_info:
            ResearchRunCreateRequest(question="Test", max_reader_papers=16)
        assert "max_reader_papers" in str(exc_info.value)

    def test_max_reader_papers_validation_valid_range(self):
        """测试 max_reader_papers 在 3-15 范围内都有效"""
        for val in [3, 8, 15]:
            req = ResearchRunCreateRequest(question="Test", max_reader_papers=val)
            assert req.max_reader_papers == val

    def test_source_mode_validation(self):
        """测试 source_mode 必须是三种之一"""
        with pytest.raises(ValidationError):
            ResearchRunCreateRequest(question="Test", source_mode="invalid")

    def test_defaults(self):
        """测试所有默认值"""
        req = ResearchRunCreateRequest(question="Test")
        assert req.source_mode == "hybrid"
        assert req.max_reader_papers == 8
        assert req.reader_concurrency == 3
        assert req.zotero_collection_key is None
        assert req.year_start is None
        assert req.year_end is None
        assert req.venue_filter == []
        assert req.keywords == []


class TestPaperCandidate:
    """测试 PaperCandidate schema"""

    def test_minimal_candidate(self):
        """测试最小字段"""
        candidate = PaperCandidate(
            paper_id="paper_001",
            source="semantic_scholar",
            title="Test Paper",
        )
        assert candidate.paper_id == "paper_001"
        assert candidate.source == "semantic_scholar"
        assert candidate.title == "Test Paper"
        assert candidate.authors == []
        assert candidate.metadata == {}

    def test_all_fields(self):
        """测试所有字段"""
        candidate = PaperCandidate(
            paper_id="paper_001",
            source="arxiv",
            title="Test Paper",
            authors=["Alice", "Bob"],
            year=2024,
            venue="ACL",
            abstract="This is a test.",
            doi="10.1234/test",
            arxiv_id="2401.12345",
            semantic_scholar_id="abc123",
            zotero_item_id="ZOTERO123",
            url="https://example.com",
            pdf_url="https://example.com/paper.pdf",
            local_pdf_path="/path/to/paper.pdf",
            citation_count=42,
            relevance_score=0.95,
            metadata={"key": "value"},
        )
        assert candidate.authors == ["Alice", "Bob"]
        assert candidate.year == 2024
        assert candidate.citation_count == 42
        assert candidate.relevance_score == 0.95

    def test_source_validation(self):
        """测试 source 必须是三种之一"""
        with pytest.raises(ValidationError):
            PaperCandidate(
                paper_id="paper_001",
                source="invalid_source",
                title="Test",
            )


class TestPaperCard:
    """测试 PaperCard schema"""

    def test_minimal_card(self):
        """测试最小字段"""
        card = PaperCard(
            paper_id="paper_001",
            status="completed",
            extraction_mode="pdf",
            title="Test Paper",
        )
        assert card.paper_id == "paper_001"
        assert card.status == "completed"
        assert card.extraction_mode == "pdf"
        assert card.title == "Test Paper"
        assert card.research_problem == ""
        assert card.datasets == []
        assert card.claims == []

    def test_all_fields(self):
        """测试所有字段"""
        card = PaperCard(
            paper_id="paper_001",
            status="completed",
            extraction_mode="pdf",
            title="Test Paper",
            bibliographic_metadata={"authors": ["Alice"]},
            research_problem="How to solve X?",
            method="We propose Y.",
            datasets=["Dataset A", "Dataset B"],
            metrics=["F1", "Accuracy"],
            key_results=["Result 1", "Result 2"],
            limitations=["Limitation 1"],
            assumptions=["Assumption 1"],
            future_work=["Future 1"],
            claims=[{"text": "Claim 1"}],
            evidence=[{"snippet": "Evidence 1"}],
            error=None,
        )
        assert card.research_problem == "How to solve X?"
        assert len(card.datasets) == 2
        assert len(card.key_results) == 2

    def test_status_validation(self):
        """测试 status 必须是五种之一"""
        with pytest.raises(ValidationError):
            PaperCard(
                paper_id="paper_001",
                status="invalid",
                extraction_mode="pdf",
                title="Test",
            )

    def test_extraction_mode_validation(self):
        """测试 extraction_mode 必须是两种之一"""
        with pytest.raises(ValidationError):
            PaperCard(
                paper_id="paper_001",
                status="completed",
                extraction_mode="invalid",
                title="Test",
            )


class TestReportClaim:
    """测试 ReportClaim schema"""

    def test_minimal_claim(self):
        """测试最小字段"""
        claim = ReportClaim(
            claim_text="Test claim",
            claim_type="result",
            verification_status="supported",
        )
        assert claim.claim_text == "Test claim"
        assert claim.claim_type == "result"
        assert claim.verification_status == "supported"
        assert claim.citation_ids == []
        assert claim.verification_reason == ""

    def test_all_fields(self):
        """测试所有字段"""
        claim = ReportClaim(
            claim_text="Method X achieves 95% accuracy",
            claim_type="result",
            citation_ids=["paper_001", "paper_002"],
            evidence_ids=["ev_001", "ev_002"],
            verification_status="numeric_trace_missing",
            verification_reason="No table or figure reference found",
        )
        assert len(claim.citation_ids) == 2
        assert claim.verification_status == "numeric_trace_missing"
        assert "table" in claim.verification_reason

    def test_claim_type_validation(self):
        """测试 claim_type 包含所有类型"""
        valid_types = ["method", "dataset", "metric", "result", "limitation", "gap", "other"]
        for claim_type in valid_types:
            claim = ReportClaim(
                claim_text="Test",
                claim_type=claim_type,
                verification_status="supported",
            )
            assert claim.claim_type == claim_type

    def test_verification_status_all_values(self):
        """测试 verification_status 包含 PRD 要求的五种状态"""
        statuses = [
            "supported",
            "weak",
            "unverified",
            "numeric_trace_missing",
            "conflict_detected",
        ]
        for status in statuses:
            claim = ReportClaim(
                claim_text="Test",
                claim_type="result",
                verification_status=status,
            )
            assert claim.verification_status == status


class TestResearchStage:
    """测试 ResearchStage schema"""

    def test_minimal_stage(self):
        """测试最小字段"""
        stage = ResearchStage(
            id="stage_001",
            run_id="run_001",
            stage="planner",
            status="queued",
            created_at=datetime.now(),
        )
        assert stage.stage == "planner"
        assert stage.status == "queued"
        assert stage.progress == 0.0
        assert stage.message == ""

    def test_all_fields(self):
        """测试所有字段"""
        now = datetime.now()
        stage = ResearchStage(
            id="stage_001",
            run_id="run_001",
            stage="reader",
            status="running",
            progress=0.5,
            message="Processing paper 3/5",
            started_at=now,
            completed_at=None,
            error=None,
            created_at=now,
        )
        assert stage.progress == 0.5
        assert "3/5" in stage.message
        assert stage.started_at is not None


class TestResearchEvent:
    """测试 ResearchEvent schema"""

    def test_minimal_event(self):
        """测试最小字段"""
        event = ResearchEvent(
            id="event_001",
            run_id="run_001",
            stage="planner",
            level="info",
            message="Plan generated",
            created_at=datetime.now(),
        )
        assert event.level == "info"
        assert event.message == "Plan generated"
        assert event.payload == {}

    def test_with_payload(self):
        """测试带 payload 的事件"""
        event = ResearchEvent(
            id="event_001",
            run_id="run_001",
            stage="retriever",
            level="warning",
            message="API timeout",
            payload={"source": "semantic_scholar", "retry": 1},
            created_at=datetime.now(),
        )
        assert event.payload["source"] == "semantic_scholar"
        assert event.payload["retry"] == 1

    def test_runner_event_stage(self):
        """Runner-level events should be valid for run detail responses."""
        event = ResearchEvent(
            id="event_runner_001",
            run_id="run_001",
            stage="runner",
            level="error",
            message="Pipeline execution failed",
            created_at=datetime.now(),
        )
        assert event.stage == "runner"


class TestResearchPlan:
    """测试 ResearchPlan schema"""

    def test_minimal_plan(self):
        """测试最小字段"""
        plan = ResearchPlan(
            id="plan_001",
            run_id="run_001",
            version=1,
            phase="initial",
            plan_data={},
            created_at=datetime.now(),
        )
        assert plan.version == 1
        assert plan.phase == "initial"
        assert plan.plan_data == {}

    def test_with_plan_data(self):
        """测试带计划数据的 plan"""
        plan = ResearchPlan(
            id="plan_001",
            run_id="run_001",
            version=1,
            phase="initial",
            plan_data={
                "normalized_question": "What is RAG?",
                "subquestions": ["Q1", "Q2"],
                "queries": ["query1", "query2"],
            },
            created_at=datetime.now(),
        )
        assert "normalized_question" in plan.plan_data
        assert len(plan.plan_data["queries"]) == 2


class TestResearchReport:
    """测试 ResearchReport schema"""

    def test_minimal_report(self):
        """测试最小字段"""
        report = ResearchReport(
            id="report_001",
            run_id="run_001",
            status="completed",
            markdown="# Report",
            template_version="v1",
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )
        assert report.status == "completed"
        assert report.markdown == "# Report"
        assert report.template_version == "v1"


class TestResearchRunCreateResponse:
    """测试 ResearchRunCreateResponse schema"""

    def test_create_response(self):
        """测试创建响应"""
        now = datetime.now()
        response = ResearchRunCreateResponse(
            run_id="rp_20260621_001",
            status="queued",
            created_at=now,
        )
        assert response.run_id == "rp_20260621_001"
        assert response.status == "queued"
        assert response.created_at == now


class TestResearchRunListResponse:
    """测试 ResearchRunListResponse schema"""

    def test_empty_list(self):
        """测试空列表"""
        response = ResearchRunListResponse(count=0, runs=[])
        assert response.count == 0
        assert response.runs == []

    def test_with_runs(self):
        """测试带运行记录的列表"""
        now = datetime.now()
        response = ResearchRunListResponse(
            count=2,
            runs=[
                ResearchRunSummary(
                    run_id="run_001",
                    question="Test question 1",
                    source_mode="web_search",
                    status="completed",
                    error=None,
                    created_at=now.isoformat(),
                ),
                ResearchRunSummary(
                    run_id="run_002",
                    question="Test question 2",
                    source_mode="zotero_only",
                    status="running",
                    error=None,
                    created_at=now.isoformat(),
                ),
            ],
        )
        assert response.count == 2
        assert len(response.runs) == 2


class TestResearchRunDetailResponse:
    """测试 ResearchRunDetailResponse schema"""

    def test_minimal_detail(self):
        """测试最小字段"""
        now = datetime.now()
        detail = ResearchRunDetailResponse(
            run_id="run_001",
            question="What is RAG?",
            source_mode="hybrid",
            status="running",
            max_reader_papers=8,
            reader_concurrency=3,
            created_at=now,
            stages=[],
            events=[],
            candidates=[],
            cards=[],
        )
        assert detail.run_id == "run_001"
        assert detail.question == "What is RAG?"
        assert detail.status == "running"
        assert detail.stages == []
        assert detail.candidates == []

    def test_full_detail(self):
        """测试完整字段"""
        now = datetime.now()
        detail = ResearchRunDetailResponse(
            run_id="run_001",
            question="What is RAG?",
            normalized_question="Normalized: What is RAG?",
            source_mode="hybrid",
            zotero_collection_key="ABC123",
            status="completed",
            max_reader_papers=8,
            reader_concurrency=3,
            year_start=2020,
            year_end=2025,
            venue_filter=["ACL"],
            keywords=["RAG"],
            created_at=now,
            started_at=now,
            completed_at=now,
            stages=[],
            events=[],
            candidates=[],
            cards=[],
            plan=None,
            report=None,
            error=None,
        )
        assert detail.normalized_question == "Normalized: What is RAG?"
        assert detail.zotero_collection_key == "ABC123"
        assert detail.year_start == 2020
