"""FailureDetector — threshold-based detection of retrieval / QA / comparison failures."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class FailureCase:
    failure_type: str
    sample_id: str | None
    reason: str
    context: dict[str, Any] = field(default_factory=dict)


class FailureDetector:
    def __init__(
        self,
        retrieval_score_threshold: float = 0.5,
        qa_pass_score_threshold: float = 0.5,
        comparison_completeness_threshold: float = 0.7,
    ) -> None:
        self.retrieval_threshold = retrieval_score_threshold
        self.qa_threshold = qa_pass_score_threshold
        self.comparison_threshold = comparison_completeness_threshold

    def detect_retrieval_failure(
        self,
        query: str,
        results: list[dict[str, Any]],
        sample_id: str | None = None,
    ) -> FailureCase | None:
        if not results:
            return FailureCase(
                failure_type="retrieval_no_results",
                sample_id=sample_id,
                reason="empty retrieval results",
                context={"query": query[:160]},
            )
        best_score = max(
            (float(r.get("score", 0.0) or 0.0) for r in results), default=0.0
        )
        if best_score < self.retrieval_threshold:
            return FailureCase(
                failure_type="retrieval_low_score",
                sample_id=sample_id,
                reason=f"top score {best_score:.3f} below threshold {self.retrieval_threshold}",
                context={
                    "query": query[:160],
                    "top_score": best_score,
                    "num_results": len(results),
                },
            )
        relevant_count = sum(1 for r in results if r.get("is_relevant"))
        if relevant_count == 0:
            return FailureCase(
                failure_type="retrieval_irrelevant",
                sample_id=sample_id,
                reason="no chunk flagged as relevant",
                context={"query": query[:160], "num_results": len(results)},
            )
        return None

    def detect_qa_failure(
        self,
        question: str,
        answer: str,
        answer_evaluation: dict[str, Any] | None = None,
        citation_evaluation: dict[str, Any] | None = None,
        sample_id: str | None = None,
    ) -> FailureCase | None:
        if not answer or not answer.strip():
            return FailureCase(
                failure_type="qa_empty_answer",
                sample_id=sample_id,
                reason="model returned empty answer",
                context={"question": question[:160]},
            )
        if answer_evaluation is not None:
            score = float(answer_evaluation.get("score", 0.0) or 0.0)
            passed = bool(answer_evaluation.get("passed"))
            if not passed and score < self.qa_threshold:
                return FailureCase(
                    failure_type="qa_low_score",
                    sample_id=sample_id,
                    reason=f"answer score {score:.3f} below threshold {self.qa_threshold}",
                    context={
                        "question": question[:160],
                        "score": score,
                        "answer": answer[:200],
                    },
                )
        if citation_evaluation is not None:
            cite_score = float(citation_evaluation.get("score", 0.0) or 0.0)
            if not citation_evaluation.get("passed") and cite_score < self.qa_threshold:
                return FailureCase(
                    failure_type="qa_bad_citation",
                    sample_id=sample_id,
                    reason=f"citation score {cite_score:.3f} below threshold",
                    context={"question": question[:160], "citation_score": cite_score},
                )
        return None

    def detect_comparison_failure(
        self,
        comparison_result: dict[str, Any],
        sample_id: str | None = None,
    ) -> FailureCase | None:
        completeness = float(comparison_result.get("completeness", 1.0) or 0.0)
        if completeness < self.comparison_threshold:
            return FailureCase(
                failure_type="comparison_incomplete",
                sample_id=sample_id,
                reason=f"completeness {completeness:.3f} below threshold {self.comparison_threshold}",
                context={
                    "completeness": completeness,
                    "evidence_quality": comparison_result.get("evidence_quality"),
                    "section_alignment": comparison_result.get("section_alignment"),
                },
            )
        evidence_quality = float(comparison_result.get("evidence_quality", 1.0) or 0.0)
        if evidence_quality < self.comparison_threshold:
            return FailureCase(
                failure_type="comparison_weak_evidence",
                sample_id=sample_id,
                reason=f"evidence quality {evidence_quality:.3f} below threshold",
                context={"evidence_quality": evidence_quality},
            )
        return None

    def record(
        self,
        case: FailureCase | None,
        collector: Any | None = None,
    ) -> FailureCase | None:
        if case is None or collector is None:
            return case
        try:
            collector.log_failure(
                failure_type=case.failure_type,
                context={"sample_id": case.sample_id, **(case.context or {})},
                reason=case.reason,
            )
        except Exception:  # pragma: no cover - best effort
            pass
        return case
