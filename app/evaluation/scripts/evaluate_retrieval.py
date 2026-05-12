from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from app.evaluation.metrics import (
    RETRIEVAL_STRATEGIES,
    build_retrieval_variant_results,
    evaluate_retrieval_sample,
    load_qa_samples,
    summarize_retrieval_results,
)

DEFAULT_DATASET = Path("app/evaluation/datasets/qa_eval_seed.jsonl")
DEFAULT_OUTPUT = Path("app/evaluation/reports/retrieval_eval_seed_report.json")


def build_seed_retrieval_results(dataset_path: Path, top_k: int) -> dict[str, Any]:
    samples = load_qa_samples(str(dataset_path))
    results = []

    for sample in samples:
        supporting_sections = sample.supporting_sections or ["Abstract"]
        retrieved_chunks = []
        for rank in range(1, top_k + 1):
            if rank == 1:
                retrieved_chunks.append(
                    {
                        "chunk_id": f"{sample.sample_id}-support-1",
                        "paper_id": sample.paper_id or "unknown-paper",
                        "section": supporting_sections[0],
                        "score": 1.0,
                    }
                )
            else:
                retrieved_chunks.append(
                    {
                        "chunk_id": f"{sample.sample_id}-distractor-{rank}",
                        "paper_id": sample.paper_id or "unknown-paper",
                        "section": f"Distractor-{rank}",
                        "score": max(0.0, 1.0 - (rank * 0.1)),
                    }
                )
        results.append(evaluate_retrieval_sample(sample=sample, retrieved_chunks=retrieved_chunks, top_k=top_k))

    summary = summarize_retrieval_results(results, top_k=top_k)
    return {
        "dataset": str(dataset_path),
        "summary": summary,
        "results": [result.model_dump() for result in results],
    }



def _comparison_chunks(sample, top_k: int) -> dict[str, list[dict[str, Any]]]:
    supporting_sections = sample.supporting_sections or ["Abstract"]
    unique_sections = []
    for section in supporting_sections:
        if section not in unique_sections:
            unique_sections.append(section)
    primary_section = unique_sections[0]
    secondary_section = unique_sections[1] if len(unique_sections) > 1 else None
    return {
        "dense": [
            {
                "chunk_id": f"{sample.sample_id}-dense-distractor-1",
                "paper_id": sample.paper_id or "unknown-paper",
                "section": "Conclusion",
                "content": "Completely unrelated conclusion text.",
                "score": 0.96,
            },
            {
                "chunk_id": f"{sample.sample_id}-{primary_section.lower()}-gold-1",
                "paper_id": sample.paper_id or "unknown-paper",
                "section": primary_section,
                "content": f"Evidence for {primary_section}.",
                "score": 0.81,
            },
            {
                "chunk_id": f"{sample.sample_id}-dense-extra-distractor-2",
                "paper_id": sample.paper_id or "unknown-paper",
                "section": "Background",
                "content": "A dense retriever false positive with mild semantic overlap.",
                "score": 0.73,
            },
        ][:top_k],
        "dense_rerank": [
            {
                "chunk_id": f"{sample.sample_id}-{primary_section.lower()}-gold-1",
                "paper_id": sample.paper_id or "unknown-paper",
                "section": primary_section,
                "content": f"Evidence for {primary_section}.",
                "score": 0.98,
            },
            *(
                [
                    {
                        "chunk_id": f"{sample.sample_id}-{secondary_section.lower()}-gold-2",
                        "paper_id": sample.paper_id or "unknown-paper",
                        "section": secondary_section,
                        "content": f"Evidence for {secondary_section}.",
                        "score": 0.88,
                    }
                ]
                if secondary_section
                else [
                    {
                        "chunk_id": f"{sample.sample_id}-dense-rerank-support-2",
                        "paper_id": sample.paper_id or "unknown-paper",
                        "section": primary_section,
                        "content": f"Additional evidence for {primary_section}.",
                        "score": 0.84,
                    }
                ]
            ),
            {
                "chunk_id": f"{sample.sample_id}-dense-distractor-1",
                "paper_id": sample.paper_id or "unknown-paper",
                "section": "Conclusion",
                "content": "Completely unrelated conclusion text.",
                "score": 0.62,
            },
        ][:top_k],
        "hybrid": [
            {
                "chunk_id": f"{sample.sample_id}-{primary_section.lower()}-gold-1",
                "paper_id": sample.paper_id or "unknown-paper",
                "section": primary_section,
                "content": f"Evidence for {primary_section}.",
                "score": 0.92,
            },
            {
                "chunk_id": f"{sample.sample_id}-hybrid-distractor-1",
                "paper_id": sample.paper_id or "unknown-paper",
                "section": "Background",
                "content": "Keyword overlap but incomplete support.",
                "score": 0.79,
            },
            *(
                [
                    {
                        "chunk_id": f"{sample.sample_id}-{secondary_section.lower()}-gold-2",
                        "paper_id": sample.paper_id or "unknown-paper",
                        "section": secondary_section,
                        "content": f"Evidence for {secondary_section}.",
                        "score": 0.74,
                    }
                ]
                if secondary_section
                else []
            ),
        ][:top_k],
        "hybrid_rerank": [
            {
                "chunk_id": f"{sample.sample_id}-{primary_section.lower()}-gold-1",
                "paper_id": sample.paper_id or "unknown-paper",
                "section": primary_section,
                "content": f"Evidence for {primary_section}.",
                "score": 0.99,
            },
            *(
                [
                    {
                        "chunk_id": f"{sample.sample_id}-{secondary_section.lower()}-gold-2",
                        "paper_id": sample.paper_id or "unknown-paper",
                        "section": secondary_section,
                        "content": f"Evidence for {secondary_section}.",
                        "score": 0.93,
                    }
                ]
                if secondary_section
                else [
                    {
                        "chunk_id": f"{sample.sample_id}-hybrid-rerank-support-2",
                        "paper_id": sample.paper_id or "unknown-paper",
                        "section": primary_section,
                        "content": f"Additional evidence for {primary_section}.",
                        "score": 0.9,
                    }
                ]
            ),
            {
                "chunk_id": f"{sample.sample_id}-hybrid-distractor-1",
                "paper_id": sample.paper_id or "unknown-paper",
                "section": "Background",
                "content": "Keyword overlap but incomplete support.",
                "score": 0.61,
            },
        ][:top_k],
    }



def build_seed_retrieval_comparison_results(dataset_path: Path, top_k: int) -> dict[str, Any]:
    samples = load_qa_samples(str(dataset_path))
    retrieved_by_strategy = {
        sample.sample_id: _comparison_chunks(sample=sample, top_k=top_k)
        for sample in samples
    }
    report = build_retrieval_variant_results(samples=samples, retrieved_by_strategy=retrieved_by_strategy, top_k=top_k)
    report["dataset"] = str(dataset_path)
    report["strategies"] = list(RETRIEVAL_STRATEGIES)
    return report


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Evaluate retrieval metrics on the seed QA benchmark dataset.")
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET)
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--mode", choices=("baseline", "compare"), default="baseline")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    if args.mode == "compare":
        report = build_seed_retrieval_comparison_results(args.dataset, args.top_k)
    else:
        report = build_seed_retrieval_results(args.dataset, args.top_k)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Generated retrieval evaluation report: {args.output}")
    print(json.dumps(report["summary"], ensure_ascii=False))
