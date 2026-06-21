"""
Test Synthesis Agent

测试报告综合生成逻辑。
"""

import json
from datetime import datetime

import pytest

from app.research_pipeline.agents.synthesis import SynthesisAgent
from app.research_pipeline.schemas import PaperCard


@pytest.fixture
def sample_initial_plan():
    """Sample initial plan."""
    return {
        "normalized_question": "What are the latest methods for few-shot learning?",
        "subquestions": [
            "What are the main approaches to few-shot learning?",
            "Which datasets are commonly used?",
        ],
        "queries": ["few-shot learning methods", "meta-learning"],
        "relevance_criteria": ["proposes new few-shot method", "evaluates on miniImageNet"],
    }


@pytest.fixture
def sample_candidate_selection_plan():
    """Sample candidate selection plan."""
    return {
        "selected_paper_ids": ["paper_20260621_001", "paper_20260621_002"],
        "selection_reasoning": "Both papers propose novel few-shot learning methods.",
    }


@pytest.fixture
def sample_paper_cards():
    """Sample PaperCards."""
    return [
        PaperCard(
            paper_id="paper_20260621_001",
            status="completed",
            extraction_mode="pdf",
            title="ProtoNet: Prototypical Networks for Few-shot Learning",
            bibliographic_metadata={
                "authors": ["Jake Snell", "Kevin Swersky", "Richard Zemel"],
                "year": 2017,
                "venue": "NeurIPS",
            },
            research_problem="Few-shot learning with limited labeled data",
            method="Prototypical Networks using metric learning",
            datasets=["miniImageNet", "Omniglot"],
            metrics=["accuracy", "F1-score"],
            key_results=["Achieved 68.2% accuracy on miniImageNet 5-way 5-shot"],
            limitations=["Requires careful distance metric selection"],
            assumptions=["Embedding space is well-structured"],
            future_work=["Explore non-Euclidean metrics"],
            claims=[
                {
                    "claim_text": "ProtoNet achieves 68.2% on miniImageNet 5-way 5-shot",
                    "claim_type": "result",
                }
            ],
            evidence=[],
        ),
        PaperCard(
            paper_id="paper_20260621_002",
            status="completed",
            extraction_mode="abstract_only",
            title="MAML: Model-Agnostic Meta-Learning",
            bibliographic_metadata={
                "authors": ["Chelsea Finn", "Pieter Abbeel", "Sergey Levine"],
                "year": 2017,
                "venue": "ICML",
            },
            research_problem="Meta-learning for rapid adaptation",
            method="Gradient-based meta-learning",
            datasets=["miniImageNet"],
            metrics=["accuracy"],
            key_results=["Achieved 63.1% on miniImageNet 5-way 5-shot"],
            limitations=["Computationally expensive second-order gradients"],
            assumptions=["Model parameters are differentiable"],
            future_work=["First-order approximations"],
            claims=[
                {
                    "claim_text": "MAML achieves 63.1% on miniImageNet 5-way 5-shot",
                    "claim_type": "result",
                }
            ],
            evidence=[],
        ),
    ]


def test_synthesis_agent_structure(tmp_path, sample_initial_plan, sample_candidate_selection_plan, sample_paper_cards):
    """Test that synthesis agent generates report with 8 required sections."""
    db_path = str(tmp_path / "test.db")
    agent = SynthesisAgent(db_path=db_path, llm_client=None)

    report_md = agent.execute(
        initial_plan=sample_initial_plan,
        candidate_selection_plan=sample_candidate_selection_plan,
        paper_cards=sample_paper_cards,
        evidence=[],
    )

    # Must be a string
    assert isinstance(report_md, str)
    assert len(report_md) > 0

    # Must have all 8 sections
    assert "## 1. Research Question" in report_md
    assert "## 2. Methodology Landscape" in report_md
    assert "## 3. Dataset And Metric Comparison" in report_md
    assert "## 4. SOTA And Key Results" in report_md
    assert "## 5. Limitations And Failure Modes" in report_md
    assert "## 6. Conflicts Or Inconsistent Findings" in report_md
    assert "## 7. Research Gaps" in report_md
    assert "## 8. References" in report_md


def test_synthesis_agent_references_only_reader_papers(
    tmp_path, sample_initial_plan, sample_candidate_selection_plan, sample_paper_cards
):
    """Test that References section only includes papers that entered Reader."""
    db_path = str(tmp_path / "test.db")
    agent = SynthesisAgent(db_path=db_path, llm_client=None)

    report_md = agent.execute(
        initial_plan=sample_initial_plan,
        candidate_selection_plan=sample_candidate_selection_plan,
        paper_cards=sample_paper_cards,
        evidence=[],
    )

    # Extract References section
    ref_start = report_md.find("## 8. References")
    assert ref_start != -1

    ref_section = report_md[ref_start:]

    # Must mention both paper_ids that were in PaperCards
    assert "paper_20260621_001" in ref_section
    assert "paper_20260621_002" in ref_section

    # Must include paper titles
    assert "ProtoNet" in ref_section or "Prototypical Networks" in ref_section
    assert "MAML" in ref_section


def test_synthesis_agent_fallback_skeleton(
    tmp_path, sample_initial_plan, sample_candidate_selection_plan, sample_paper_cards
):
    """Test that agent generates deterministic skeleton when LLM unavailable."""
    db_path = str(tmp_path / "test.db")
    # llm_client=None triggers fallback
    agent = SynthesisAgent(db_path=db_path, llm_client=None)

    report_md = agent.execute(
        initial_plan=sample_initial_plan,
        candidate_selection_plan=sample_candidate_selection_plan,
        paper_cards=sample_paper_cards,
        evidence=[],
    )

    # Skeleton should clearly mark it needs manual synthesis
    assert "[自动综合不可用]" in report_md or "LLM 不可用" in report_md or "skeleton" in report_md.lower()

    # Skeleton should still have structure
    assert "## 1. Research Question" in report_md
    assert "## 8. References" in report_md


def test_synthesis_agent_empty_paper_cards(tmp_path, sample_initial_plan, sample_candidate_selection_plan):
    """Test synthesis with no paper cards."""
    db_path = str(tmp_path / "test.db")
    agent = SynthesisAgent(db_path=db_path, llm_client=None)

    report_md = agent.execute(
        initial_plan=sample_initial_plan,
        candidate_selection_plan=sample_candidate_selection_plan,
        paper_cards=[],
        evidence=[],
    )

    # Should still generate structure
    assert "## 1. Research Question" in report_md
    assert "## 8. References" in report_md

    # References should indicate no papers
    ref_start = report_md.find("## 8. References")
    ref_section = report_md[ref_start:]
    assert "无" in ref_section or "None" in ref_section or "暂无" in ref_section


def test_synthesis_agent_citation_format(
    tmp_path, sample_initial_plan, sample_candidate_selection_plan, sample_paper_cards
):
    """Test that citations use [CITE:paper_id] format when present."""
    db_path = str(tmp_path / "test.db")
    agent = SynthesisAgent(db_path=db_path, llm_client=None)

    report_md = agent.execute(
        initial_plan=sample_initial_plan,
        candidate_selection_plan=sample_candidate_selection_plan,
        paper_cards=sample_paper_cards,
        evidence=[],
    )

    # Fallback skeleton might not have citations, but if it does, they should be correct format
    # This test is more relevant when LLM is available, but we verify the format is possible
    if "[CITE:" in report_md:
        # If citations exist, they should reference valid paper_ids
        assert "[CITE:paper_20260621_001]" in report_md or "[CITE:paper_20260621_002]" in report_md
