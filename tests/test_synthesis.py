from datetime import datetime, timezone

from app.research_workflow.schemas import (
    ResearchRun,
    ResearchRunPaperItem,
    build_default_steps,
)
from app.research_workflow.synthesis import KnowledgePackSynthesisService


def _run_with_papers():
    now = datetime.now(timezone.utc)
    return ResearchRun(
        run_id="run_20260611_000001",
        collection_id="COLL123",
        collection_name="IRSTD",
        goal="Generate a literature review and experiment plan.",
        steps=build_default_steps(),
        paper_items=[
            ResearchRunPaperItem(
                item_id="zotero_A1",
                title="Grounding DINO for Infrared Small Target Detection",
                zotero_item_id="A1",
                paper_id="paper_001",
                status="completed",
                progress=1.0,
                metadata={
                    "year": 2025,
                    "doi": "10.1234/a",
                    "method": "open-vocabulary detector adaptation",
                    "dataset": "IRSTD-1k",
                },
                created_at=now,
                updated_at=now,
            ),
            ResearchRunPaperItem(
                item_id="zotero_B2",
                title="Hybrid Retrieval for Scientific QA",
                zotero_item_id="B2",
                paper_id="paper_002",
                status="completed",
                progress=1.0,
                metadata={"year": 2024, "url": "https://example.test/b"},
                created_at=now,
                updated_at=now,
            ),
            ResearchRunPaperItem(
                item_id="zotero_C3",
                title="Missing PDF Paper",
                zotero_item_id="C3",
                status="skipped",
                progress=1.0,
                error="No local PDF attachment found",
                created_at=now,
                updated_at=now,
            ),
        ],
        created_at=now,
        updated_at=now,
    )


def test_synthesis_generates_expected_knowledge_pack_files():
    result = KnowledgePackSynthesisService().generate(_run_with_papers())

    assert [item.filename for item in result.files] == [
        "01 Literature Review.md",
        "02 Method Matrix.md",
        "03 Research Gaps.md",
        "04 Experiment Plan.md",
        "05 Reading Roadmap.md",
    ]
    assert [item.label for item in result.files] == [
        "Literature Review",
        "Method Matrix",
        "Research Gaps",
        "Experiment Plan",
        "Reading Roadmap",
    ]
    assert result.completed_paper_count == 2
    assert result.skipped_or_failed_count == 1


def test_synthesis_outputs_include_evidence_links():
    result = KnowledgePackSynthesisService().generate(_run_with_papers())
    combined = "\n".join(item.content for item in result.files)

    assert "Zotero `A1`" in combined
    assert "Paper `paper_001`" in combined
    assert "DOI `10.1234/a`" in combined
    assert "Zotero `B2`" in combined
    assert "Paper `paper_002`" in combined
    assert "https://example.test/b" in combined
    assert "Missing PDF Paper" in combined
    assert "No local PDF attachment found" in combined


def test_experiment_plan_is_actionable():
    result = KnowledgePackSynthesisService().generate(_run_with_papers())
    experiment_plan = next(
        item.content for item in result.files if item.label == "Experiment Plan"
    )

    for token in (
        "## Objective",
        "## Dataset",
        "## Baseline",
        "## Metrics",
        "## Next Actions",
        "recall@k",
        "completed papers",
        "Select two completed papers",
    ):
        assert token in experiment_plan
