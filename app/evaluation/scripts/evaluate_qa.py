from __future__ import annotations

import json
import logging
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from statistics import mean
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from app.evaluation.judges import JudgeResult, build_judges
from app.evaluation.metrics import load_qa_samples
from app.evaluation.schemas import QAEvalSample

logger = logging.getLogger(__name__)

DEFAULT_DATASET = Path("app/evaluation/datasets/qa_eval_seed.jsonl")
DEFAULT_OUTPUT = Path("app/evaluation/reports/qa_eval_seed_report.json")


@dataclass
class QAEvaluationResult:
    sample_id: str
    question: str
    mode: str
    predicted_answer: str
    citations: list[dict[str, Any]]
    answer_evaluation: JudgeResult
    citation_evaluation: JudgeResult

    def model_dump(self) -> dict[str, Any]:
        return {
            "sample_id": self.sample_id,
            "question": self.question,
            "mode": self.mode,
            "predicted_answer": self.predicted_answer,
            "citations": self.citations,
            "answer_evaluation": asdict(self.answer_evaluation),
            "citation_evaluation": asdict(self.citation_evaluation),
        }


def build_seed_qa_predictions(sample: QAEvalSample) -> dict[str, Any]:
    supporting_sections = sample.supporting_sections or ["Abstract"]
    citations = [
        {
            "paper_id": sample.paper_id or "unknown-paper",
            "section": section,
            "chunk_id": f"{sample.sample_id}-{index}",
            "title": sample.paper_title or sample.paper_id or "Unknown",
        }
        for index, section in enumerate(supporting_sections, start=1)
    ]
    return {
        "predicted_answer": sample.expected_answer,
        "citations": citations,
    }


def build_live_qa_predictions(
    sample: QAEvalSample,
    vector_store: Any,
    embedding_client: Any,
    llm_client: Any,
    top_k: int = 5,
) -> dict[str, Any]:
    """Run the real paper_qa.answer_question pipeline against a single sample.

    Returns a dict shaped like build_seed_qa_predictions for downstream consumption.
    On error returns an empty answer so the judge can record a failure.
    """
    from app.services.paper_qa import answer_question

    try:
        result = answer_question(
            question=sample.question,
            vector_store=vector_store,
            embedding_client=embedding_client,
            llm_client=llm_client,
            paper_id=sample.paper_id,
            top_k=top_k,
        )
    except Exception as exc:
        logger.exception("Live QA pipeline failed for sample %s: %s", sample.sample_id, exc)
        return {"predicted_answer": "", "citations": []}

    sources = result.get("sources", []) or []
    citations = [
        {
            "paper_id": src.get("paper_id", sample.paper_id or "unknown-paper"),
            "section": src.get("section", "Unknown"),
            "chunk_id": src.get("chunk_id", f"{sample.sample_id}-live-{idx}"),
            "title": src.get("title", sample.paper_title or "Unknown"),
            "score": src.get("score"),
        }
        for idx, src in enumerate(sources, start=1)
    ]
    return {
        "predicted_answer": result.get("answer", ""),
        "citations": citations,
    }


def _build_live_pipeline_clients() -> tuple[Any, Any, Any]:
    """Construct VectorStore + EmbeddingClient + LLMClient using current settings."""
    from app.services.embedding_client import EmbeddingClient
    from app.services.llm_client import LLMClient
    from app.services.vector_store import VectorStore

    return VectorStore(), EmbeddingClient(), LLMClient()


def evaluate_qa_sample(
    sample: QAEvalSample,
    prediction: dict[str, Any],
    answer_judge: Any,
    citation_judge: Any,
    mode: str,
) -> QAEvaluationResult:
    predicted_answer = prediction.get("predicted_answer", "")
    citations = prediction.get("citations", [])
    answer_result = answer_judge.evaluate(sample=sample, predicted_answer=predicted_answer, citations=citations)
    citation_result = citation_judge.evaluate(sample=sample, citations=citations, predicted_answer=predicted_answer)
    return QAEvaluationResult(
        sample_id=sample.sample_id,
        question=sample.question,
        mode=mode,
        predicted_answer=predicted_answer,
        citations=citations,
        answer_evaluation=answer_result,
        citation_evaluation=citation_result,
    )


def summarize_qa_results(results: list[QAEvaluationResult], mode: str) -> dict[str, Any]:
    sample_count = len(results)
    answer_scores = [result.answer_evaluation.score for result in results]
    citation_scores = [result.citation_evaluation.score for result in results]
    answer_passes = sum(1 for result in results if result.answer_evaluation.passed)
    citation_passes = sum(1 for result in results if result.citation_evaluation.passed)
    return {
        "sample_count": sample_count,
        "evaluation_mode": mode,
        "answer_pass_rate": answer_passes / sample_count if sample_count else 0.0,
        "citation_pass_rate": citation_passes / sample_count if sample_count else 0.0,
        "mean_answer_score": mean(answer_scores) if answer_scores else 0.0,
        "mean_citation_score": mean(citation_scores) if citation_scores else 0.0,
    }


def evaluate_qa_dataset(
    dataset_path: Path,
    mode: str = "rule_based",
    use_live_pipeline: bool = False,
    top_k: int = 5,
) -> dict[str, Any]:
    answer_judge, citation_judge = build_judges(mode=mode)
    samples = load_qa_samples(str(dataset_path))

    live_clients: tuple[Any, Any, Any] | None = None
    if use_live_pipeline:
        live_clients = _build_live_pipeline_clients()
        logger.info("Live QA pipeline enabled: VectorStore + EmbeddingClient + LLMClient initialized")

    results = []
    for sample in samples:
        if use_live_pipeline and live_clients is not None:
            vs, ec, lc = live_clients
            prediction = build_live_qa_predictions(
                sample, vector_store=vs, embedding_client=ec, llm_client=lc, top_k=top_k
            )
        else:
            prediction = build_seed_qa_predictions(sample)
        results.append(
            evaluate_qa_sample(
                sample=sample,
                prediction=prediction,
                answer_judge=answer_judge,
                citation_judge=citation_judge,
                mode=mode,
            )
        )

    return {
        "dataset": str(dataset_path),
        "pipeline": "live" if use_live_pipeline else "stub",
        "summary": summarize_qa_results(results, mode=mode),
        "results": [result.model_dump() for result in results],
    }


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Evaluate offline QA answer/citation quality scaffolding.")
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET)
    parser.add_argument("--mode", type=str, default="rule_based")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--use-live-pipeline",
        action="store_true",
        help="Call the real paper_qa.answer_question pipeline instead of the deterministic stub.",
    )
    parser.add_argument("--top-k", type=int, default=5, help="top_k for live retrieval (only used with --use-live-pipeline)")
    args = parser.parse_args()

    report = evaluate_qa_dataset(
        dataset_path=args.dataset,
        mode=args.mode,
        use_live_pipeline=args.use_live_pipeline,
        top_k=args.top_k,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Generated QA evaluation report: {args.output}")
    print(json.dumps(report["summary"], ensure_ascii=False))
