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


def _pick_sections(paper: PaperRecord) -> list[dict]:
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
    return ordered[:2]


def build_qa_samples(papers: Iterable[PaperRecord]) -> list[QAEvalSample]:
    samples: list[QAEvalSample] = []
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

        for index, section in enumerate(_pick_sections(paper), start=1):
            samples.append(
                QAEvalSample(
                    sample_id=f"{paper.paper_id}-section-{index}",
                    question=f"According to the '{section['heading']}' section of '{paper.title}', what key information is highlighted?",
                    expected_answer=_clean_text(section["content"], max_length=320),
                    paper_id=paper.paper_id,
                    paper_title=paper.title,
                    supporting_sections=[section["heading"]],
                    difficulty="medium",
                    metadata={
                        "source": "seed",
                        "generation_type": "section",
                        "source_paper_title": paper.title,
                        "source_pdf": paper.pdf_path,
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


def build_seed_dataset(metadata_dir: Path = DEFAULT_METADATA_DIR, output_dir: Path = DEFAULT_OUTPUT_DIR) -> tuple[Path, Path]:
    papers = _load_papers(metadata_dir)
    if not papers:
        raise RuntimeError(f"No parsed metadata files found in {metadata_dir}")

    qa_samples = build_qa_samples(papers)
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
    args = parser.parse_args()

    qa_path, comparison_path = build_seed_dataset(args.metadata_dir, args.output_dir)
    print(f"Generated QA seed dataset: {qa_path}")
    print(f"Generated comparison seed dataset: {comparison_path}")
