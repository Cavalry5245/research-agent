from __future__ import annotations

import json
from statistics import mean
from typing import Any

from app.evaluation.schemas import ComparisonEvalSample, QAEvalSample, RetrievalEvalResult, RetrievalMatch

RETRIEVAL_STRATEGIES = ("dense", "dense_rerank", "hybrid", "hybrid_rerank")


def normalize_section_name(value: str) -> str:
    return " ".join((value or "").strip().lower().split())


def compute_retrieval_metrics(
    retrieved_chunk_ids: list[str],
    relevant_chunk_ids: set[str],
    top_k: int,
) -> dict[str, Any]:
    top_results = retrieved_chunk_ids[:top_k]
    first_relevant_rank: int | None = None
    hits = 0

    for rank, chunk_id in enumerate(top_results, start=1):
        if chunk_id in relevant_chunk_ids:
            hits += 1
            if first_relevant_rank is None:
                first_relevant_rank = rank

    relevant_total = len(relevant_chunk_ids)
    hit_at_k = first_relevant_rank is not None
    recall_at_k = hits / relevant_total if relevant_total else 0.0
    mrr = 1.0 / first_relevant_rank if first_relevant_rank else 0.0

    return {
        "hit_at_k": hit_at_k,
        "recall_at_k": recall_at_k,
        "mrr": mrr,
        "first_relevant_rank": first_relevant_rank,
        "relevant_retrieved": hits,
        "relevant_total": relevant_total,
    }


def evaluate_retrieval_sample(
    sample: QAEvalSample,
    retrieved_chunks: list[dict[str, Any]],
    top_k: int,
) -> RetrievalEvalResult:
    relevant_sections = {normalize_section_name(section) for section in sample.supporting_sections}
    relevant_chunk_ids: set[str] = set()
    matches: list[RetrievalMatch] = []
    matched_relevant_sections: set[str] = set()

    for rank, chunk in enumerate(retrieved_chunks[:top_k], start=1):
        normalized_section = normalize_section_name(chunk.get("section", ""))
        is_relevant = (
            (sample.paper_id is None or chunk.get("paper_id") == sample.paper_id)
            and normalized_section in relevant_sections
        )
        if is_relevant and chunk.get("chunk_id"):
            relevant_chunk_ids.add(chunk["chunk_id"])
            matched_relevant_sections.add(normalized_section)
        matches.append(
            RetrievalMatch(
                chunk_id=chunk.get("chunk_id", f"missing-{rank}"),
                paper_id=chunk.get("paper_id", "unknown"),
                section=chunk.get("section", "Unknown"),
                score=float(chunk.get("score", 0.0)),
                rank=rank,
                is_relevant=is_relevant,
            )
        )

    metrics = compute_retrieval_metrics(
        retrieved_chunk_ids=[match.chunk_id for match in matches],
        relevant_chunk_ids=relevant_chunk_ids,
        top_k=top_k,
    )

    relevant_section_count = len(relevant_sections)
    recall_at_k = len(matched_relevant_sections) / relevant_section_count if relevant_section_count else 0.0

    return RetrievalEvalResult(
        sample_id=sample.sample_id,
        query=sample.question,
        top_k=top_k,
        hit_at_k=metrics["hit_at_k"],
        recall_at_k=recall_at_k,
        mrr=metrics["mrr"],
        retrieved_chunks=matches,
    )


def summarize_retrieval_results(results: list[RetrievalEvalResult], top_k: int) -> dict[str, Any]:
    sample_count = len(results)
    hit_values = [1.0 if result.hit_at_k else 0.0 for result in results]
    recall_values = [result.recall_at_k for result in results]
    mrr_values = [result.mrr for result in results]
    hits = int(sum(hit_values))

    return {
        "sample_count": sample_count,
        "top_k": top_k,
        "hit_rate": mean(hit_values) if hit_values else 0.0,
        "mean_recall": mean(recall_values) if recall_values else 0.0,
        "mrr": mean(mrr_values) if mrr_values else 0.0,
        "hits": hits,
        "misses": sample_count - hits,
    }


def build_retrieval_variant_results(
    samples: list[QAEvalSample],
    retrieved_by_strategy: dict[str, dict[str, list[dict[str, Any]]]],
    top_k: int,
) -> dict[str, Any]:
    results_by_strategy: dict[str, list[RetrievalEvalResult]] = {strategy: [] for strategy in RETRIEVAL_STRATEGIES}

    for sample in samples:
        strategy_results = retrieved_by_strategy.get(sample.sample_id, {})
        for strategy in RETRIEVAL_STRATEGIES:
            retrieved_chunks = strategy_results.get(strategy)
            if not retrieved_chunks:
                continue
            results_by_strategy[strategy].append(
                evaluate_retrieval_sample(sample=sample, retrieved_chunks=retrieved_chunks, top_k=top_k)
            )

    strategy_summaries = {
        strategy: summarize_retrieval_results(results, top_k=top_k)
        for strategy, results in results_by_strategy.items()
        if results
    }

    baseline_strategy = "dense"
    baseline_summary = strategy_summaries.get(baseline_strategy, {"hit_rate": 0.0, "mean_recall": 0.0, "mrr": 0.0})
    improvements: dict[str, dict[str, float]] = {}
    for strategy, summary in strategy_summaries.items():
        if strategy == baseline_strategy:
            continue
        improvements[strategy] = {
            "hit_rate_delta_vs_dense": summary["hit_rate"] - baseline_summary["hit_rate"],
            "mean_recall_delta_vs_dense": summary["mean_recall"] - baseline_summary["mean_recall"],
            "mrr_delta_vs_dense": summary["mrr"] - baseline_summary["mrr"],
        }

    best_strategy = None
    if strategy_summaries:
        best_strategy = max(
            strategy_summaries.items(),
            key=lambda item: (item[1]["mrr"], item[1]["mean_recall"], item[1]["hit_rate"]),
        )[0]

    return {
        "summary": {
            "sample_count": len(samples),
            "top_k": top_k,
            "strategy_count": len(strategy_summaries),
            "baseline_strategy": baseline_strategy,
            "best_strategy": best_strategy,
            "improvements": improvements,
        },
        "strategy_summaries": strategy_summaries,
        "results_by_strategy": {
            strategy: [result.model_dump() for result in results]
            for strategy, results in results_by_strategy.items()
            if results
        },
    }


def load_qa_samples(dataset_path: str) -> list[QAEvalSample]:
    rows: list[QAEvalSample] = []
    with open(dataset_path, "r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            rows.append(QAEvalSample.model_validate(json.loads(line)))
    return rows


def load_comparison_samples(dataset_path: str) -> list[ComparisonEvalSample]:
    rows: list[ComparisonEvalSample] = []
    with open(dataset_path, "r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            rows.append(ComparisonEvalSample.model_validate(json.loads(line)))
    return rows
