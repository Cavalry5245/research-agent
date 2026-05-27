from __future__ import annotations

import json
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from statistics import mean
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from app.evaluation.metrics import load_comparison_samples
from app.evaluation.reporting import (
    build_comparison_report_markdown,
    build_comparison_report_payload,
)
from app.schemas import CompareBatchRunResult, PaperComparisonResult
from app.services.paper_compare import compare_papers_batch, save_compare_batch_result

DEFAULT_DATASET = Path("app/evaluation/datasets/comparison_eval_seed.jsonl")
DEFAULT_OUTPUT = Path("app/evaluation/reports/comparison_eval_seed_report.json")
DEFAULT_MARKDOWN_OUTPUT = Path("app/evaluation/reports/comparison_eval_seed_report.md")
DEFAULT_COMPARE_OUTPUT = Path(
    "app/evaluation/reports/comparison_eval_seed_predictions.json"
)
DEFAULT_METADATA_DIR = Path("app/storage/metadata")


@dataclass
class ComparisonEvaluationResult:
    sample_id: str
    question: str
    expected_aspects: list[str]
    predicted_aspects: list[str]
    missing_aspects: list[str]
    aspects_with_missing_evidence: list[str]
    paper_coverage: dict[str, bool]
    paper_alignment: dict[str, float]
    completeness: float
    evidence_completeness: float
    evidence_quality: float
    section_alignment: float
    paper_balance: float
    evidence_quality_issues: list[str]
    section_alignment_issues: list[str]
    paper_alignment_issues: dict[str, list[str]]
    comparison_source: str
    uses_structured_summaries: bool

    def model_dump(self) -> dict[str, Any]:
        return {
            "sample_id": self.sample_id,
            "question": self.question,
            "expected_aspects": self.expected_aspects,
            "predicted_aspects": self.predicted_aspects,
            "missing_aspects": self.missing_aspects,
            "aspects_with_missing_evidence": self.aspects_with_missing_evidence,
            "paper_coverage": self.paper_coverage,
            "paper_alignment": self.paper_alignment,
            "completeness": self.completeness,
            "evidence_completeness": self.evidence_completeness,
            "evidence_quality": self.evidence_quality,
            "section_alignment": self.section_alignment,
            "paper_balance": self.paper_balance,
            "evidence_quality_issues": self.evidence_quality_issues,
            "section_alignment_issues": self.section_alignment_issues,
            "paper_alignment_issues": self.paper_alignment_issues,
            "comparison_source": self.comparison_source,
            "uses_structured_summaries": self.uses_structured_summaries,
        }


def _build_seed_predicted_comparison(sample: Any) -> dict[str, Any]:
    aspects = []
    for aspect in sample.comparison_aspects:
        evidence = []
        per_paper = {}
        for paper_id, paper_title in zip(
            sample.paper_ids, sample.paper_titles, strict=False
        ):
            sections = sample.supporting_sections.get(paper_id, [])
            if sections:
                per_paper[paper_id] = f"基于{sections[0]}提取的{aspect}信息"
                evidence.append(
                    {
                        "paper_id": paper_id,
                        "paper_title": paper_title,
                        "section": sections[0],
                        "snippet": f"{paper_title} 在 {sections[0]} 中提供了 {aspect} 依据。",
                    }
                )
            else:
                per_paper[paper_id] = "未明确说明"

        aspects.append(
            {
                "name": aspect,
                "summary": f"围绕 {aspect} 的结构化对比。",
                "key_differences": [],
                "per_paper": per_paper,
                "evidence": evidence,
            }
        )

    return {
        "overview": sample.expected_summary,
        "aspects": aspects,
        "markdown": "# deterministic comparison stub",
    }


def _normalize_text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip().lower()


def _aspect_evidence_matches(aspect: Any) -> bool:
    if not aspect.evidence:
        return False

    relevant_values = [
        _normalize_text(value)
        for value in aspect.per_paper.values()
        if _normalize_text(value) and _normalize_text(value) != "未明确说明"
    ]
    if not relevant_values:
        return False

    evidence_sections = {
        _normalize_text(item.section)
        for item in aspect.evidence
        if _normalize_text(item.section)
    }
    aspect_name = _normalize_text(getattr(aspect, "name", ""))
    snippets = " ".join(_normalize_text(item.snippet) for item in aspect.evidence)
    return any(
        value in snippets
        or value in evidence_sections
        or (aspect_name and aspect_name in snippets)
        for value in relevant_values
    )


def _aspect_sections_align(aspect: Any, sample: Any) -> bool:
    if not aspect.evidence:
        return False

    aligned_by_paper = _aspect_paper_alignment(aspect, sample)
    if not aligned_by_paper:
        return True
    return all(score >= 1.0 for score in aligned_by_paper.values())


def _aspect_paper_alignment(aspect: Any, sample: Any) -> dict[str, float]:
    aligned_by_paper: dict[str, float] = {}
    relevant_paper_ids = [
        paper_id
        for paper_id, value in aspect.per_paper.items()
        if _normalize_text(paper_id)
        and _normalize_text(value)
        and _normalize_text(value) != "未明确说明"
    ]

    for paper_id in relevant_paper_ids:
        expected_sections = {
            _normalize_text(section)
            for section in sample.supporting_sections.get(paper_id, [])
            if _normalize_text(section)
        }
        evidence_sections = {
            _normalize_text(item.section)
            for item in aspect.evidence
            if _normalize_text(getattr(item, "paper_id", None))
            == _normalize_text(paper_id)
            and _normalize_text(item.section)
        }

        if not expected_sections:
            aligned_by_paper[paper_id] = 1.0
            continue
        if not evidence_sections:
            aligned_by_paper[paper_id] = 0.0
            continue

        aligned_by_paper[paper_id] = (
            1.0 if bool(evidence_sections & expected_sections) else 0.0
        )

    return aligned_by_paper


def _load_predicted_comparison(sample: Any) -> tuple[PaperComparisonResult, str]:
    raw = sample.metadata.get("predicted_comparison")
    if raw:
        return PaperComparisonResult.model_validate(raw), "predicted_comparison"
    return (
        PaperComparisonResult.model_validate(_build_seed_predicted_comparison(sample)),
        "deterministic_stub",
    )


def evaluate_comparison_dataset(dataset_path: Path) -> dict[str, Any]:
    samples = load_comparison_samples(str(dataset_path))
    results: list[ComparisonEvaluationResult] = []

    for sample in samples:
        comparison, comparison_source = _load_predicted_comparison(sample)
        predicted_aspects = [aspect.name for aspect in comparison.aspects]
        expected_aspects = list(sample.comparison_aspects)

        missing_aspects = [
            aspect for aspect in expected_aspects if aspect not in predicted_aspects
        ]
        aspects_with_missing_evidence = []
        for aspect_name in expected_aspects:
            aspect = next(
                (item for item in comparison.aspects if item.name == aspect_name), None
            )
            if aspect is None or not aspect.evidence:
                aspects_with_missing_evidence.append(aspect_name)

        evidence_quality_issues = []
        section_alignment_issues = []
        paper_alignment: dict[str, float] = {
            paper_id: 0.0 for paper_id in sample.paper_ids
        }
        paper_alignment_counts: dict[str, int] = {
            paper_id: 0 for paper_id in sample.paper_ids
        }
        paper_alignment_issues: dict[str, list[str]] = {}
        for aspect_name in expected_aspects:
            aspect = next(
                (item for item in comparison.aspects if item.name == aspect_name), None
            )
            if aspect is None or not aspect.evidence:
                continue
            if not _aspect_evidence_matches(aspect):
                evidence_quality_issues.append(aspect_name)
            aspect_paper_alignment = _aspect_paper_alignment(aspect, sample)
            for paper_id, score in aspect_paper_alignment.items():
                paper_alignment[paper_id] = paper_alignment.get(paper_id, 0.0) + score
                paper_alignment_counts[paper_id] = (
                    paper_alignment_counts.get(paper_id, 0) + 1
                )
            misaligned_papers = [
                paper_id
                for paper_id, score in aspect_paper_alignment.items()
                if score < 1.0
            ]
            if misaligned_papers:
                section_alignment_issues.append(aspect_name)
                paper_alignment_issues[aspect_name] = misaligned_papers

        paper_coverage: dict[str, bool] = {}
        for paper_id in sample.paper_ids:
            covered = any(
                aspect.per_paper.get(paper_id, "未明确说明") != "未明确说明"
                for aspect in comparison.aspects
                if aspect.name in expected_aspects
            )
            paper_coverage[paper_id] = covered

        for paper_id in sample.paper_ids:
            if paper_alignment_counts.get(paper_id):
                paper_alignment[paper_id] = (
                    paper_alignment[paper_id] / paper_alignment_counts[paper_id]
                )
            else:
                paper_alignment[paper_id] = 1.0

        total_aspects = len(expected_aspects)
        completeness = (
            (total_aspects - len(missing_aspects)) / total_aspects
            if total_aspects
            else 0.0
        )
        evidence_completeness = (
            (total_aspects - len(aspects_with_missing_evidence)) / total_aspects
            if total_aspects
            else 0.0
        )
        evidence_quality = (
            (total_aspects - len(evidence_quality_issues)) / total_aspects
            if total_aspects
            else 0.0
        )
        section_alignment = (
            sum(paper_alignment.values()) / len(paper_alignment)
            if paper_alignment
            else 0.0
        )
        paper_balance = (
            sum(1 for covered in paper_coverage.values() if covered)
            / len(sample.paper_ids)
            if sample.paper_ids
            else 0.0
        )

        results.append(
            ComparisonEvaluationResult(
                sample_id=sample.sample_id,
                question=sample.question,
                expected_aspects=expected_aspects,
                predicted_aspects=predicted_aspects,
                missing_aspects=missing_aspects,
                aspects_with_missing_evidence=aspects_with_missing_evidence,
                paper_coverage=paper_coverage,
                paper_alignment=paper_alignment,
                completeness=completeness,
                evidence_completeness=evidence_completeness,
                evidence_quality=evidence_quality,
                section_alignment=section_alignment,
                paper_balance=paper_balance,
                evidence_quality_issues=evidence_quality_issues,
                section_alignment_issues=section_alignment_issues,
                paper_alignment_issues=paper_alignment_issues,
                comparison_source=comparison_source,
                uses_structured_summaries=bool(comparison.structured_summaries),
            )
        )

    summary = {
        "sample_count": len(results),
        "mean_completeness": (
            mean([result.completeness for result in results]) if results else 0.0
        ),
        "mean_evidence_completeness": (
            mean([result.evidence_completeness for result in results])
            if results
            else 0.0
        ),
        "mean_evidence_quality": (
            mean([result.evidence_quality for result in results]) if results else 0.0
        ),
        "mean_section_alignment": (
            mean([result.section_alignment for result in results]) if results else 0.0
        ),
        "mean_paper_balance": (
            mean([result.paper_balance for result in results]) if results else 0.0
        ),
    }

    return {
        "dataset": str(dataset_path),
        "summary": summary,
        "results": [result.model_dump() for result in results],
    }


def generate_live_compare_predictions(
    dataset_path: Path,
    metadata_dir: Path,
    output_path: Path,
    llm_client: Any = None,
    compare_batch_script: Path | None = None,
) -> CompareBatchRunResult:
    if compare_batch_script is not None:
        completed = subprocess.run(
            [
                sys.executable,
                str(compare_batch_script),
                str(dataset_path),
                str(output_path),
            ],
            capture_output=True,
            text=True,
            cwd=str(REPO_ROOT),
        )
        if completed.stdout:
            print(completed.stdout, end="")
        if completed.stderr:
            print(completed.stderr, file=sys.stderr, end="")
        if completed.returncode != 0:
            raise RuntimeError(
                "compare batch helper failed with exit code "
                f"{completed.returncode}\nSTDOUT:\n{completed.stdout}\nSTDERR:\n{completed.stderr}"
            )
        return CompareBatchRunResult.model_validate_json(
            output_path.read_text(encoding="utf-8")
        )

    result = compare_papers_batch(
        dataset_path=str(dataset_path),
        metadata_dir=str(metadata_dir),
        llm_client=llm_client,
    )
    save_compare_batch_result(result, str(output_path))
    return result


def inject_live_compare_predictions(
    dataset_path: Path,
    compare_output_path: Path,
) -> list[dict[str, Any]]:
    batch_result = CompareBatchRunResult.model_validate_json(
        compare_output_path.read_text(encoding="utf-8")
    )
    comparison_by_sample_id = {
        sample_result.sample_id: sample_result.comparison.model_dump(mode="json")
        for sample_result in batch_result.results
    }

    original_rows = [
        json.loads(line)
        for line in dataset_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    updated_rows: list[dict[str, Any]] = []

    dataset_sample_ids = {row.get("sample_id") for row in original_rows}
    batch_sample_ids = set(comparison_by_sample_id)
    unmatched_sample_ids = [
        sample_id
        for sample_id in batch_sample_ids
        if sample_id not in dataset_sample_ids
    ]
    missing_prediction_sample_ids = [
        sample_id
        for sample_id in dataset_sample_ids
        if sample_id not in batch_sample_ids
    ]
    if unmatched_sample_ids:
        raise ValueError(
            "Live compare payload contains sample_ids not found in dataset: "
            + ", ".join(sorted(unmatched_sample_ids))
        )
    if missing_prediction_sample_ids:
        raise ValueError(
            "Dataset contains sample_ids missing from live compare payload: "
            + ", ".join(sorted(missing_prediction_sample_ids))
        )

    for row in original_rows:
        metadata = row.setdefault("metadata", {})
        sample_id = row.get("sample_id")
        predicted_comparison = comparison_by_sample_id.get(sample_id)
        if predicted_comparison is not None:
            metadata["predicted_comparison"] = predicted_comparison
        updated_rows.append(row)

    dataset_path.write_text(
        "\n".join(json.dumps(row, ensure_ascii=False) for row in updated_rows) + "\n",
        encoding="utf-8",
    )
    return updated_rows


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Evaluate structured multi-paper comparison outputs."
    )
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--markdown-output", type=Path, default=DEFAULT_MARKDOWN_OUTPUT)
    parser.add_argument("--compare-output", type=Path, default=DEFAULT_COMPARE_OUTPUT)
    parser.add_argument("--metadata-dir", type=Path, default=DEFAULT_METADATA_DIR)
    parser.add_argument(
        "--compare-batch-script",
        type=Path,
        default=None,
        help="Optional helper script that writes a compare-batch JSON to the given --compare-output path.",
    )
    parser.add_argument(
        "--generate-live-compare",
        action="store_true",
        help="Run compare service across the dataset and persist live structured comparison payloads.",
    )
    args = parser.parse_args()

    live_compare_result = None
    if args.generate_live_compare:
        live_compare_result = generate_live_compare_predictions(
            dataset_path=args.dataset,
            metadata_dir=args.metadata_dir,
            output_path=args.compare_output,
            compare_batch_script=args.compare_batch_script,
        )
        inject_live_compare_predictions(
            dataset_path=args.dataset,
            compare_output_path=args.compare_output,
        )

    report = evaluate_comparison_dataset(args.dataset)
    payload = build_comparison_report_payload(report)
    markdown = build_comparison_report_markdown(payload)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    args.markdown_output.parent.mkdir(parents=True, exist_ok=True)
    args.markdown_output.write_text(markdown, encoding="utf-8")

    print(f"Generated comparison evaluation report: {args.output}")
    print(f"Generated comparison evaluation markdown: {args.markdown_output}")
    if live_compare_result is not None:
        print(
            "Generated live comparison payloads: "
            f"{args.compare_output} ({live_compare_result.total_samples} samples)"
        )
    print(json.dumps(report["summary"], ensure_ascii=False))
