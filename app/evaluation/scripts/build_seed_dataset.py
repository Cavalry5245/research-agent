from __future__ import annotations

import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from app.evaluation.schemas import ComparisonEvalSample, QAEvalSample


DEFAULT_METADATA_DIR = Path("app/storage/metadata")
DEFAULT_OUTPUT_DIR = Path("app/evaluation/datasets")
SECTION_PRIORITY = (
    "abstract",
    "introduction",
    "method",
    "methodology",
    "approach",
    "experiment",
    "experiments",
    "results",
    "discussion",
    "conclusion",
)
COMPARISON_ASPECTS = ["task", "method", "results"]


@dataclass
class PaperRecord:
    paper_id: str
    title: str
    abstract: str
    sections: list[dict]
    pdf_path: str


def _load_papers(metadata_dir: Path) -> list[PaperRecord]:
    papers: list[PaperRecord] = []
    for path in sorted(metadata_dir.glob("*_parsed.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        papers.append(
            PaperRecord(
                paper_id=payload.get("paper_id", path.stem.replace("_parsed", "")),
                title=_clean_text(payload.get("title", "Untitled Paper")),
                abstract=_clean_text(payload.get("abstract", "")),
                sections=payload.get("sections", []),
                pdf_path=payload.get("pdf_path", ""),
            )
        )
    return papers


def _clean_text(value: str, max_length: int | None = None) -> str:
    cleaned = re.sub(r"\s+", " ", value or "").strip()
    if max_length and len(cleaned) > max_length:
        return cleaned[: max_length - 3].rstrip() + "..."
    return cleaned


def _normalize_heading(heading: str) -> str:
    return re.sub(r"[^a-z]+", "", (heading or "").lower())


def _pick_sections(paper: PaperRecord, max_sections: int = 2) -> list[dict]:
    preferred: list[dict] = []
    remaining: list[dict] = []
    for section in paper.sections:
        heading = _clean_text(section.get("heading", "Section"))
        content = _clean_text(section.get("content", ""), max_length=600)
        if not heading or not content:
            continue
        item = {"heading": heading, "content": content}
        normalized = _normalize_heading(heading)
        if any(token in normalized for token in SECTION_PRIORITY if token != "abstract"):
            preferred.append(item)
        else:
            remaining.append(item)
    ordered = preferred + remaining
    return ordered[:max_sections]


def build_qa_samples(papers: Iterable[PaperRecord], max_sections_per_paper: int = 2) -> list[QAEvalSample]:
    samples: list[QAEvalSample] = []
    question_templates = [
        "According to the '{section}' section of '{title}', what key information is highlighted?",
        "Summarize the main points from the '{section}' section of '{title}'.",
        "What does '{title}' describe in its '{section}' section?",
    ]
    for paper in papers:
        if paper.abstract:
            samples.append(
                QAEvalSample(
                    sample_id=f"{paper.paper_id}-abstract",
                    question=f"What does the paper '{paper.title}' mainly propose or study?",
                    expected_answer=_clean_text(paper.abstract, max_length=320),
                    paper_id=paper.paper_id,
                    paper_title=paper.title,
                    supporting_sections=["Abstract"],
                    difficulty="easy",
                    metadata={
                        "source": "seed",
                        "generation_type": "abstract",
                        "source_paper_title": paper.title,
                        "source_pdf": paper.pdf_path,
                    },
                )
            )
            # Paraphrased abstract question (medium difficulty)
            samples.append(
                QAEvalSample(
                    sample_id=f"{paper.paper_id}-abstract-paraphrased",
                    question=f"In one paragraph, what is the central contribution of '{paper.title}'?",
                    expected_answer=_clean_text(paper.abstract, max_length=320),
                    paper_id=paper.paper_id,
                    paper_title=paper.title,
                    supporting_sections=["Abstract"],
                    difficulty="medium",
                    metadata={
                        "source": "seed",
                        "generation_type": "abstract_paraphrase",
                        "source_paper_title": paper.title,
                        "source_pdf": paper.pdf_path,
                    },
                )
            )

        sections = _pick_sections(paper, max_sections=max_sections_per_paper)
        for index, section in enumerate(sections, start=1):
            for template_idx, template in enumerate(question_templates):
                samples.append(
                    QAEvalSample(
                        sample_id=f"{paper.paper_id}-section-{index}-v{template_idx + 1}",
                        question=template.format(section=section["heading"], title=paper.title),
                        expected_answer=_clean_text(section["content"], max_length=320),
                        paper_id=paper.paper_id,
                        paper_title=paper.title,
                        supporting_sections=[section["heading"]],
                        difficulty="medium" if template_idx == 0 else "hard",
                        metadata={
                            "source": "seed",
                            "generation_type": "section",
                            "template_variant": template_idx + 1,
                            "source_paper_title": paper.title,
                            "source_pdf": paper.pdf_path,
                        },
                    )
                )
    return samples


def build_hard_qa_samples(papers: Iterable[PaperRecord]) -> list[QAEvalSample]:
    """Generate intentionally harder samples to expose real misses (e.g. cross-section synthesis,
    out-of-scope queries). These yield non-perfect metrics so the evaluation reports become useful."""
    samples: list[QAEvalSample] = []
    out_of_scope_topics = [
        "blockchain consensus protocols",
        "Quantum supremacy benchmarks",
        "Tax policy in developing economies",
    ]
    for idx, paper in enumerate(papers):
        samples.append(
            QAEvalSample(
                sample_id=f"{paper.paper_id}-hard-synthesis",
                question=f"Compare the methodology and the reported main results in '{paper.title}', focusing on quantitative metrics.",
                expected_answer=_clean_text(paper.abstract, max_length=320) if paper.abstract else "Detailed methodology and metrics required.",
                paper_id=paper.paper_id,
                paper_title=paper.title,
                supporting_sections=["Method", "Results"],
                difficulty="hard",
                metadata={
                    "source": "seed",
                    "generation_type": "cross_section_synthesis",
                    "source_paper_title": paper.title,
                    "source_pdf": paper.pdf_path,
                },
            )
        )
        topic = out_of_scope_topics[idx % len(out_of_scope_topics)]
        samples.append(
            QAEvalSample(
                sample_id=f"{paper.paper_id}-hard-oos",
                question=f"Does the paper '{paper.title}' discuss {topic}? If yes, summarize the discussion.",
                expected_answer="原文未明确说明。",
                paper_id=paper.paper_id,
                paper_title=paper.title,
                supporting_sections=["Abstract"],
                difficulty="hard",
                metadata={
                    "source": "seed",
                    "generation_type": "out_of_scope_probe",
                    "source_paper_title": paper.title,
                    "source_pdf": paper.pdf_path,
                    "expected_behavior": "model should abstain",
                    "probe_topic": topic,
                },
            )
        )
    return samples


def build_comparison_samples(papers: list[PaperRecord]) -> list[ComparisonEvalSample]:
    if len(papers) < 2:
        return []

    selected = papers[: min(3, len(papers))]
    expected_summary_parts = []
    supporting_sections: dict[str, list[str]] = {}
    for paper in selected:
        section_names = [section["heading"] for section in _pick_sections(paper)] or ["Abstract"]
        supporting_sections[paper.paper_id] = section_names
        expected_summary_parts.append(
            f"{paper.title}: {_clean_text(paper.abstract, max_length=180) or 'No abstract available.'}"
        )

    sample = ComparisonEvalSample(
        sample_id="comparison-seed-001",
        question="How do these papers differ in task focus, proposed method, and reported results?",
        paper_ids=[paper.paper_id for paper in selected],
        paper_titles=[paper.title for paper in selected],
        expected_summary=" ".join(expected_summary_parts),
        comparison_aspects=COMPARISON_ASPECTS,
        supporting_sections=supporting_sections,
        metadata={
            "source": "seed",
            "generation_type": "multi_paper_comparison",
            "source_paper_ids": [paper.paper_id for paper in selected],
            "source_pdf_paths": [paper.pdf_path for paper in selected],
        },
    )
    return [sample]


def _write_jsonl(path: Path, rows: Iterable[QAEvalSample | ComparisonEvalSample]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(row.model_dump_json())
            handle.write("\n")


def build_seed_dataset(
    metadata_dir: Path = DEFAULT_METADATA_DIR,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    target_size: int | None = None,
    include_hard_samples: bool = True,
) -> tuple[Path, Path]:
    papers = _load_papers(metadata_dir)
    if not papers:
        raise RuntimeError(f"No parsed metadata files found in {metadata_dir}")

    # Auto-scale max_sections_per_paper to hit target_size when requested.
    max_sections = 2
    if target_size:
        # rough estimate: per paper we already generate 1 (abstract) + N (sections); hard pass adds 2
        hard_count = 2 * len(papers) if include_hard_samples else 0
        needed_from_sections = max(0, target_size - len(papers) - hard_count)
        per_paper_sections = max(2, -(-needed_from_sections // max(1, len(papers))))
        max_sections = per_paper_sections

    qa_samples = build_qa_samples(papers, max_sections_per_paper=max_sections)
    if include_hard_samples:
        qa_samples.extend(build_hard_qa_samples(papers))

    comparison_samples = build_comparison_samples(papers)
    if not qa_samples or not comparison_samples:
        raise RuntimeError("Unable to build the minimal seed dataset from available metadata")

    qa_path = output_dir / "qa_eval_seed.jsonl"
    comparison_path = output_dir / "comparison_eval_seed.jsonl"
    _write_jsonl(qa_path, qa_samples)
    _write_jsonl(comparison_path, comparison_samples)
    return qa_path, comparison_path


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Build a minimal benchmark seed dataset from parsed metadata.")
    parser.add_argument("--metadata-dir", type=Path, default=DEFAULT_METADATA_DIR)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--target-size", type=int, default=None, help="Target QA sample count (auto-scales sections per paper).")
    parser.add_argument("--no-hard-samples", action="store_true", help="Skip hard/out-of-scope samples.")
    args = parser.parse_args()

    qa_path, comparison_path = build_seed_dataset(
        args.metadata_dir,
        args.output_dir,
        target_size=args.target_size,
        include_hard_samples=not args.no_hard_samples,
    )
    print(f"Generated QA seed dataset: {qa_path}")
    print(f"Generated comparison seed dataset: {comparison_path}")
