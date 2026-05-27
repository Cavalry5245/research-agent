from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from typing import Any, Callable, Protocol

from app.evaluation.schemas import QAEvalSample

logger = logging.getLogger(__name__)


@dataclass
class JudgeResult:
    mode: str
    score: float
    max_score: float
    passed: bool
    reasons: list[str]
    metadata: dict[str, Any]


class AnswerJudge(Protocol):
    def evaluate(
        self,
        sample: QAEvalSample,
        predicted_answer: str,
        citations: list[dict[str, Any]] | None = None,
    ) -> JudgeResult: ...


class CitationJudge(Protocol):
    def evaluate(
        self,
        sample: QAEvalSample,
        citations: list[dict[str, Any]],
        predicted_answer: str | None = None,
    ) -> JudgeResult: ...


_TOKEN_PATTERN = re.compile(r"[a-z0-9]+")


def _normalize_text(value: str) -> str:
    return " ".join((value or "").strip().lower().split())


def _tokenize(value: str) -> list[str]:
    return _TOKEN_PATTERN.findall(_normalize_text(value))


def _unique_tokens(value: str) -> set[str]:
    return set(_tokenize(value))


class RuleBasedAnswerJudge:
    def __init__(self, min_token_recall: float = 0.35):
        self.min_token_recall = min_token_recall
        self.mode = "rule_based"

    def evaluate(
        self,
        sample: QAEvalSample,
        predicted_answer: str,
        citations: list[dict[str, Any]] | None = None,
    ) -> JudgeResult:
        expected_tokens = _unique_tokens(sample.expected_answer)
        predicted_tokens = _unique_tokens(predicted_answer)
        overlap = expected_tokens & predicted_tokens

        token_recall = len(overlap) / len(expected_tokens) if expected_tokens else 0.0
        token_precision = (
            len(overlap) / len(predicted_tokens) if predicted_tokens else 0.0
        )
        if token_precision + token_recall:
            f1 = 2 * token_precision * token_recall / (token_precision + token_recall)
        else:
            f1 = 0.0

        passed = token_recall >= self.min_token_recall
        reasons = [
            f"Token overlap coverage={token_recall:.3f}; precision={token_precision:.3f}; f1={f1:.3f}."
        ]
        if not predicted_tokens:
            reasons.append("Predicted answer was empty after normalization.")
        elif not passed:
            reasons.append(
                "Answer coverage is below the configured acceptance threshold."
            )
        else:
            reasons.append(
                "Answer achieved the minimum token-overlap coverage threshold."
            )

        return JudgeResult(
            mode=self.mode,
            score=token_recall,
            max_score=1.0,
            passed=passed,
            reasons=reasons,
            metadata={
                "token_overlap_recall": token_recall,
                "token_overlap_precision": token_precision,
                "token_overlap_f1": f1,
                "overlap_tokens": sorted(overlap),
                "expected_token_count": len(expected_tokens),
                "predicted_token_count": len(predicted_tokens),
            },
        )


class RuleBasedCitationJudge:
    def __init__(self, min_section_coverage: float = 0.5):
        self.min_section_coverage = min_section_coverage
        self.mode = "rule_based"

    def evaluate(
        self,
        sample: QAEvalSample,
        citations: list[dict[str, Any]],
        predicted_answer: str | None = None,
    ) -> JudgeResult:
        expected_sections = {
            _normalize_text(section) for section in sample.supporting_sections
        }
        citation_sections = {
            _normalize_text(citation.get("section", "")) for citation in citations
        }
        matched_sections = sorted(expected_sections & citation_sections)
        section_coverage = (
            len(matched_sections) / len(expected_sections) if expected_sections else 0.0
        )
        matched_paper_id = (
            any(citation.get("paper_id") == sample.paper_id for citation in citations)
            if sample.paper_id
            else True
        )
        passed = section_coverage >= self.min_section_coverage and matched_paper_id

        reasons = [
            f"Supporting section coverage={section_coverage:.3f} ({len(matched_sections)}/{len(expected_sections) or 0})."
        ]
        if not matched_paper_id:
            reasons.append("No citation matched the expected paper_id.")
        elif not passed:
            reasons.append(
                "Supporting section coverage is below the configured acceptance threshold."
            )
        else:
            reasons.append(
                "Citations cover the expected supporting sections for the sample."
            )

        return JudgeResult(
            mode=self.mode,
            score=section_coverage,
            max_score=1.0,
            passed=passed,
            reasons=reasons,
            metadata={
                "expected_supporting_sections": sorted(expected_sections),
                "matched_supporting_sections": matched_sections,
                "citation_section_count": len(citation_sections),
                "matched_paper_id": matched_paper_id,
            },
        )


class PlaceholderLLMJudge:
    def __init__(self):
        self.mode = "placeholder_llm"

    def evaluate(
        self,
        sample: QAEvalSample,
        predicted_answer: str = "",
        citations: list[dict[str, Any]] | None = None,
    ) -> JudgeResult:
        return JudgeResult(
            mode=self.mode,
            score=0.0,
            max_score=1.0,
            passed=False,
            reasons=[
                "Placeholder LLM judge is an extension point only; wire a real model-backed judge in a later phase."
            ],
            metadata={
                "status": "not_implemented",
                "expected_interface": {
                    "question": sample.question,
                    "expected_answer": sample.expected_answer,
                    "predicted_answer": predicted_answer,
                    "citations": citations or [],
                },
            },
        )


_JSON_BLOCK_RE = re.compile(r"\{.*\}", re.DOTALL)


def _parse_judge_json(raw: str) -> dict[str, Any]:
    """Parse JSON from LLM output, tolerant of markdown code fences and prefixes."""
    if not raw:
        return {}
    text = raw.strip()
    # Strip ```json ... ``` fences if present
    if text.startswith("```"):
        text = re.sub(r"^```[a-zA-Z]*\n?", "", text)
        text = re.sub(r"\n?```$", "", text)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    # Fallback: extract the first {...} block
    match = _JSON_BLOCK_RE.search(text)
    if match:
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            pass
    return {}


def _coerce_score(value: Any) -> float:
    try:
        score = float(value)
    except (TypeError, ValueError):
        return 0.0
    if score < 0.0:
        return 0.0
    if score > 1.0:
        return 1.0
    return score


class LLMAnswerJudge:
    """LLM-as-judge for answer quality. Compares predicted vs expected answer semantically.

    `llm_call` is a callable that takes a prompt string and returns the LLM response text.
    Defaults to `LLMClient().generate_text` if not provided (lazy import to avoid
    requiring LLM_API_KEY at module load time, which would break unit tests).
    """

    def __init__(
        self, pass_threshold: float = 0.5, llm_call: Callable[[str], str] | None = None
    ):
        self.mode = "llm"
        self.pass_threshold = pass_threshold
        self._llm_call = llm_call

    def _get_llm_call(self) -> Callable[[str], str]:
        if self._llm_call is not None:
            return self._llm_call
        from app.services.llm_client import LLMClient

        client = LLMClient()
        self._llm_call = client.generate_text
        return self._llm_call

    def evaluate(
        self,
        sample: QAEvalSample,
        predicted_answer: str,
        citations: list[dict[str, Any]] | None = None,
    ) -> JudgeResult:
        from app.evaluation.prompts import build_answer_judge_prompt

        prompt = build_answer_judge_prompt(
            question=sample.question,
            expected_answer=sample.expected_answer,
            predicted_answer=predicted_answer,
        )
        try:
            raw = self._get_llm_call()(prompt)
        except Exception as exc:
            logger.warning(
                "LLM answer judge call failed for %s: %s", sample.sample_id, exc
            )
            return JudgeResult(
                mode=self.mode,
                score=0.0,
                max_score=1.0,
                passed=False,
                reasons=[f"LLM judge call failed: {exc}"],
                metadata={"status": "llm_error", "error": str(exc)},
            )

        parsed = _parse_judge_json(raw)
        if not parsed:
            return JudgeResult(
                mode=self.mode,
                score=0.0,
                max_score=1.0,
                passed=False,
                reasons=["Failed to parse LLM judge response as JSON."],
                metadata={"status": "parse_error", "raw_response": raw[:500]},
            )

        score = _coerce_score(parsed.get("score"))
        passed_raw = parsed.get("passed")
        passed = (
            bool(passed_raw)
            if isinstance(passed_raw, bool)
            else (score >= self.pass_threshold)
        )
        reason = str(parsed.get("reason") or "").strip()
        reasons = [reason] if reason else [f"LLM judge score={score:.3f}"]

        return JudgeResult(
            mode=self.mode,
            score=score,
            max_score=1.0,
            passed=passed,
            reasons=reasons,
            metadata={
                "status": "ok",
                "missing_points": parsed.get("missing_points") or [],
                "incorrect_points": parsed.get("incorrect_points") or [],
                "raw_response_chars": len(raw),
            },
        )


class LLMCitationJudge:
    """LLM-as-judge for citation quality. Verifies citations support the answer.

    Shares the same `llm_call` injection pattern as LLMAnswerJudge.
    """

    def __init__(
        self, pass_threshold: float = 0.5, llm_call: Callable[[str], str] | None = None
    ):
        self.mode = "llm"
        self.pass_threshold = pass_threshold
        self._llm_call = llm_call

    def _get_llm_call(self) -> Callable[[str], str]:
        if self._llm_call is not None:
            return self._llm_call
        from app.services.llm_client import LLMClient

        client = LLMClient()
        self._llm_call = client.generate_text
        return self._llm_call

    def evaluate(
        self,
        sample: QAEvalSample,
        citations: list[dict[str, Any]],
        predicted_answer: str | None = None,
    ) -> JudgeResult:
        from app.evaluation.prompts import build_citation_judge_prompt

        prompt = build_citation_judge_prompt(
            question=sample.question,
            predicted_answer=predicted_answer or "",
            citations=citations or [],
            expected_sections=sample.supporting_sections or [],
            expected_paper_id=sample.paper_id,
        )
        try:
            raw = self._get_llm_call()(prompt)
        except Exception as exc:
            logger.warning(
                "LLM citation judge call failed for %s: %s", sample.sample_id, exc
            )
            return JudgeResult(
                mode=self.mode,
                score=0.0,
                max_score=1.0,
                passed=False,
                reasons=[f"LLM judge call failed: {exc}"],
                metadata={"status": "llm_error", "error": str(exc)},
            )

        parsed = _parse_judge_json(raw)
        if not parsed:
            return JudgeResult(
                mode=self.mode,
                score=0.0,
                max_score=1.0,
                passed=False,
                reasons=["Failed to parse LLM citation judge response as JSON."],
                metadata={"status": "parse_error", "raw_response": raw[:500]},
            )

        score = _coerce_score(parsed.get("score"))
        passed_raw = parsed.get("passed")
        passed = (
            bool(passed_raw)
            if isinstance(passed_raw, bool)
            else (score >= self.pass_threshold)
        )
        reason = str(parsed.get("reason") or "").strip()
        reasons = [reason] if reason else [f"LLM citation judge score={score:.3f}"]

        return JudgeResult(
            mode=self.mode,
            score=score,
            max_score=1.0,
            passed=passed,
            reasons=reasons,
            metadata={
                "status": "ok",
                "irrelevant_citations": parsed.get("irrelevant_citations") or [],
                "missing_evidence": parsed.get("missing_evidence") or [],
                "citation_count": len(citations or []),
            },
        )


def build_judges(mode: str = "rule_based") -> tuple[Any, Any]:
    normalized = _normalize_text(mode).replace(" ", "_")
    if normalized == "rule_based":
        return RuleBasedAnswerJudge(), RuleBasedCitationJudge()
    if normalized == "placeholder_llm":
        return PlaceholderLLMJudge(), PlaceholderLLMJudge()
    if normalized == "llm":
        return LLMAnswerJudge(), LLMCitationJudge()
    raise ValueError(f"Unsupported evaluation mode: {mode}")
