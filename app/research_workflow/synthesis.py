from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.research_workflow.schemas import ResearchRun, ResearchRunPaperItem


@dataclass(frozen=True)
class KnowledgePackFile:
    label: str
    filename: str
    content: str
    kind: str = "markdown"


@dataclass(frozen=True)
class SynthesisResult:
    files: list[KnowledgePackFile]
    completed_paper_count: int
    skipped_or_failed_count: int


class KnowledgePackSynthesisService:
    def generate(self, run: ResearchRun) -> SynthesisResult:
        completed = [item for item in run.paper_items if item.status == "completed"]
        skipped_or_failed = [
            item for item in run.paper_items if item.status in {"failed", "skipped"}
        ]
        evidence = [_paper_evidence(item) for item in completed]
        files = [
            KnowledgePackFile(
                label="Literature Review",
                filename="01 Literature Review.md",
                content=_literature_review(run, completed, skipped_or_failed, evidence),
            ),
            KnowledgePackFile(
                label="Method Matrix",
                filename="02 Method Matrix.md",
                content=_method_matrix(run, completed, evidence),
            ),
            KnowledgePackFile(
                label="Research Gaps",
                filename="03 Research Gaps.md",
                content=_research_gaps(run, completed, skipped_or_failed, evidence),
            ),
            KnowledgePackFile(
                label="Experiment Plan",
                filename="04 Experiment Plan.md",
                content=_experiment_plan(run, completed, evidence),
            ),
            KnowledgePackFile(
                label="Reading Roadmap",
                filename="05 Reading Roadmap.md",
                content=_reading_roadmap(run, completed, evidence),
            ),
        ]
        return SynthesisResult(
            files=files,
            completed_paper_count=len(completed),
            skipped_or_failed_count=len(skipped_or_failed),
        )


def _literature_review(
    run: ResearchRun,
    papers: list[ResearchRunPaperItem],
    skipped_or_failed: list[ResearchRunPaperItem],
    evidence: list[str],
) -> str:
    lines = [
        f"# Literature Review: {run.collection_name}",
        "",
        f"Goal: {run.goal}",
        "",
        "## Core Papers",
        "",
    ]
    if papers:
        for item, link in zip(papers, evidence, strict=False):
            lines.append(f"- {item.title} ({_year(item)}): {link}")
    else:
        lines.append("- No completed papers are available for synthesis.")
    lines.extend(["", "## Synthesis", ""])
    lines.append(
        "The completed papers are organized around method, data, and evaluation evidence "
        "captured during the ResearchAgent run."
    )
    if skipped_or_failed:
        lines.extend(["", "## Limitations", ""])
        for item in skipped_or_failed:
            lines.append(f"- {item.title}: {item.status} - {item.error or 'not processed'}")
    return "\n".join(lines) + "\n"


def _method_matrix(
    run: ResearchRun,
    papers: list[ResearchRunPaperItem],
    evidence: list[str],
) -> str:
    lines = [
        f"# Method Matrix: {run.collection_name}",
        "",
        "| Paper | Year | Method Signal | Evidence |",
        "| --- | --- | --- | --- |",
    ]
    if papers:
        for item, link in zip(papers, evidence, strict=False):
            method = item.metadata.get("method") or item.metadata.get("approach") or "Not specified"
            lines.append(f"| {item.title} | {_year(item)} | {method} | {link} |")
    else:
        lines.append("| No completed papers | - | - | - |")
    return "\n".join(lines) + "\n"


def _research_gaps(
    run: ResearchRun,
    papers: list[ResearchRunPaperItem],
    skipped_or_failed: list[ResearchRunPaperItem],
    evidence: list[str],
) -> str:
    lines = [
        f"# Research Gaps: {run.collection_name}",
        "",
        "## Candidate Gaps",
        "",
        "- Compare method robustness across datasets instead of reporting isolated scores.",
        "- Track failure cases for small, dim, or cluttered targets across papers.",
        "- Align evaluation metrics before claiming progress across methods.",
        "",
        "## Evidence Links",
        "",
    ]
    lines.extend(f"- {link}" for link in evidence)
    if skipped_or_failed:
        lines.extend(["", "## Missing Evidence", ""])
        for item in skipped_or_failed:
            lines.append(f"- {item.title}: {item.error or item.status}")
    return "\n".join(lines) + "\n"


def _experiment_plan(
    run: ResearchRun,
    papers: list[ResearchRunPaperItem],
    evidence: list[str],
) -> str:
    titles = ", ".join(item.title for item in papers) or "the completed paper set"
    lines = [
        f"# Experiment Plan: {run.collection_name}",
        "",
        "## Objective",
        f"Evaluate whether the methods represented by {titles} improve the target research goal: {run.goal}",
        "",
        "## Dataset",
        "Use the active ResearchAgent paper collection as the evidence set and pair it with the project's local benchmark dataset where available.",
        "",
        "## Baseline",
        "Start from the current retrieval and paper-processing pipeline, then compare any proposed method against the existing local vector/BM25/hybrid retrieval baselines.",
        "",
        "## Metrics",
        "- Retrieval: recall@k, precision@k, and answer faithfulness.",
        "- Synthesis: evidence coverage, contradiction count, and missing-citation count.",
        "- Workflow: completed papers, failed papers, processing time, and generated artifact count.",
        "",
        "## Next Actions",
        "- Select two completed papers as seed methods.",
        "- Build a small evaluation table from their reported datasets and metrics.",
        "- Run the local ResearchAgent QA/retrieval checks against the generated notes.",
        "- Record failure cases and update the method matrix.",
        "",
        "## Evidence",
    ]
    lines.extend(f"- {link}" for link in evidence)
    return "\n".join(lines) + "\n"


def _reading_roadmap(
    run: ResearchRun,
    papers: list[ResearchRunPaperItem],
    evidence: list[str],
) -> str:
    lines = [
        f"# Reading Roadmap: {run.collection_name}",
        "",
        "## Recommended Order",
        "",
    ]
    if papers:
        for index, (item, link) in enumerate(zip(papers, evidence, strict=False), start=1):
            lines.append(f"{index}. {item.title} - read for {_reading_focus(item)}. Evidence: {link}")
    else:
        lines.append("1. Add completed papers to generate a reading order.")
    return "\n".join(lines) + "\n"


def _paper_evidence(item: ResearchRunPaperItem) -> str:
    paper_id = item.paper_id or "not-synced"
    parts = [f"Zotero `{item.zotero_item_id}`", f"Paper `{paper_id}`"]
    doi = item.metadata.get("doi")
    url = item.metadata.get("url")
    if doi:
        parts.append(f"DOI `{doi}`")
    if url:
        parts.append(f"URL {url}")
    return " / ".join(parts)


def _year(item: ResearchRunPaperItem) -> str:
    year: Any = item.metadata.get("year")
    return str(year) if year else "n.d."


def _reading_focus(item: ResearchRunPaperItem) -> str:
    if item.metadata.get("method") or item.metadata.get("approach"):
        return "method details"
    if item.metadata.get("dataset"):
        return "dataset and evaluation setup"
    return "problem framing and evidence"
