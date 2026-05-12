import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.evaluation.schemas import QAEvalSample

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = REPO_ROOT / "app" / "evaluation" / "scripts" / "evaluate_qa.py"
QA_DATASET = REPO_ROOT / "app" / "evaluation" / "datasets" / "qa_eval_seed.jsonl"
PYTHON_EXECUTABLE = sys.executable


@pytest.fixture
def base_sample() -> QAEvalSample:
    return QAEvalSample(
        sample_id="qa-judge-1",
        question="What is proposed?",
        expected_answer="The paper proposes a retrieval augmentation method with citation support.",
        paper_id="paper-1",
        paper_title="Paper 1",
        supporting_sections=["Abstract", "Method"],
    )


def test_rule_based_answer_judge_scores_overlap_and_exposes_reasons(base_sample: QAEvalSample):
    from app.evaluation.judges import RuleBasedAnswerJudge

    judge = RuleBasedAnswerJudge()
    result = judge.evaluate(
        sample=base_sample,
        predicted_answer="The paper proposes a retrieval augmentation method with grounded citation support.",
    )

    assert result.mode == "rule_based"
    assert result.passed is True
    assert result.score > 0.6
    assert result.max_score == 1.0
    assert result.metadata["token_overlap_recall"] > 0.7
    assert result.reasons


def test_rule_based_answer_judge_fails_when_overlap_is_too_low(base_sample: QAEvalSample):
    from app.evaluation.judges import RuleBasedAnswerJudge

    judge = RuleBasedAnswerJudge(min_token_recall=0.5)
    result = judge.evaluate(sample=base_sample, predicted_answer="This discusses unrelated experiments.")

    assert result.mode == "rule_based"
    assert result.passed is False
    assert result.score < 0.5
    assert "coverage" in " ".join(result.reasons).lower()


def test_rule_based_citation_judge_scores_section_coverage(base_sample: QAEvalSample):
    from app.evaluation.judges import RuleBasedCitationJudge

    judge = RuleBasedCitationJudge()
    result = judge.evaluate(
        sample=base_sample,
        citations=[
            {"paper_id": "paper-1", "section": "Abstract", "chunk_id": "c1"},
            {"paper_id": "paper-1", "section": "Method", "chunk_id": "c2"},
            {"paper_id": "paper-2", "section": "Results", "chunk_id": "c3"},
        ],
    )

    assert result.mode == "rule_based"
    assert result.passed is True
    assert result.score == 1.0
    assert result.metadata["matched_supporting_sections"] == ["abstract", "method"]
    assert result.metadata["matched_paper_id"] is True


def test_rule_based_citation_judge_handles_missing_expected_sections(base_sample: QAEvalSample):
    from app.evaluation.judges import RuleBasedCitationJudge

    judge = RuleBasedCitationJudge(min_section_coverage=0.75)
    result = judge.evaluate(
        sample=base_sample,
        citations=[{"paper_id": "paper-1", "section": "Abstract", "chunk_id": "c1"}],
    )

    assert result.mode == "rule_based"
    assert result.passed is False
    assert result.score == 0.5
    assert "supporting section coverage" in " ".join(result.reasons).lower()


def test_placeholder_llm_judge_returns_extension_friendly_stub(base_sample: QAEvalSample):
    from app.evaluation.judges import PlaceholderLLMJudge

    judge = PlaceholderLLMJudge()
    result = judge.evaluate(
        sample=base_sample,
        predicted_answer="Stub answer",
        citations=[{"paper_id": "paper-1", "section": "Abstract"}],
    )

    assert result.mode == "placeholder_llm"
    assert result.passed is False
    assert result.score == 0.0
    assert result.metadata["status"] == "not_implemented"
    assert "extension point" in " ".join(result.reasons).lower()


def test_build_judges_supports_rule_based_and_placeholder_modes():
    from app.evaluation.judges import PlaceholderLLMJudge, RuleBasedAnswerJudge, RuleBasedCitationJudge, build_judges

    answer_judge, citation_judge = build_judges(mode="rule_based")
    assert isinstance(answer_judge, RuleBasedAnswerJudge)
    assert isinstance(citation_judge, RuleBasedCitationJudge)

    answer_judge, citation_judge = build_judges(mode="placeholder_llm")
    assert isinstance(answer_judge, PlaceholderLLMJudge)
    assert isinstance(citation_judge, PlaceholderLLMJudge)


def test_build_judges_rejects_unknown_mode():
    from app.evaluation.judges import build_judges

    with pytest.raises(ValueError, match="Unsupported evaluation mode"):
        build_judges(mode="unknown")


def test_evaluate_qa_script_emits_offline_report(tmp_path: Path):
    report_path = tmp_path / "qa_eval_report.json"

    result = subprocess.run(
        [
            PYTHON_EXECUTABLE,
            str(SCRIPT_PATH),
            "--dataset",
            str(QA_DATASET),
            "--mode",
            "rule_based",
            "--output",
            str(report_path),
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert report_path.exists(), "QA evaluation report was not generated"

    payload = json.loads(report_path.read_text(encoding="utf-8"))
    assert payload["summary"]["sample_count"] >= 1
    assert payload["summary"]["evaluation_mode"] == "rule_based"
    assert set(payload["summary"].keys()) >= {
        "answer_pass_rate",
        "citation_pass_rate",
        "mean_answer_score",
        "mean_citation_score",
    }
    assert payload["results"], "Expected per-sample QA evaluation results"
    first_result = payload["results"][0]
    assert set(first_result.keys()) >= {
        "sample_id",
        "question",
        "predicted_answer",
        "citations",
        "answer_evaluation",
        "citation_evaluation",
    }
