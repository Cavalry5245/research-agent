from __future__ import annotations

import json
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


def evaluate_qa_dataset(dataset_path: Path, mode: str = "rule_based") -> dict[str, Any]:
    answer_judge, citation_judge = build_judges(mode=mode)
    samples = load_qa_samples(str(dataset_path))
    results = []
    for sample in samples:
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
        "summary": summarize_qa_results(results, mode=mode),
        "results": [result.model_dump() for result in results],
    }


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Evaluate offline QA answer/citation quality scaffolding.")
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET)
    parser.add_argument("--mode", type=str, default="rule_based")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    report = evaluate_qa_dataset(dataset_path=args.dataset, mode=args.mode)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Generated QA evaluation report: {args.output}")
    print(json.dumps(report["summary"], ensure_ascii=False))
