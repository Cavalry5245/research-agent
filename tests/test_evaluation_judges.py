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


def test_build_judges_supports_llm_mode():
    from app.evaluation.judges import LLMAnswerJudge, LLMCitationJudge, build_judges

    answer_judge, citation_judge = build_judges(mode="llm")
    assert isinstance(answer_judge, LLMAnswerJudge)
    assert isinstance(citation_judge, LLMCitationJudge)


def test_llm_answer_judge_parses_clean_json(base_sample: QAEvalSample):
    from app.evaluation.judges import LLMAnswerJudge

    canned = '{"score": 0.85, "passed": true, "reason": "Covers main contribution", "missing_points": [], "incorrect_points": []}'
    judge = LLMAnswerJudge(llm_call=lambda prompt: canned)
    result = judge.evaluate(base_sample, predicted_answer="A retrieval augmentation method with citations.")
    assert result.mode == "llm"
    assert result.score == 0.85
    assert result.passed is True
    assert result.metadata["status"] == "ok"
    assert "Covers main contribution" in result.reasons[0]


def test_llm_answer_judge_handles_markdown_fenced_json(base_sample: QAEvalSample):
    from app.evaluation.judges import LLMAnswerJudge

    canned = '```json\n{"score": 0.2, "passed": false, "reason": "Missed key points", "missing_points": ["x"]}\n```'
    judge = LLMAnswerJudge(llm_call=lambda prompt: canned)
    result = judge.evaluate(base_sample, predicted_answer="off-topic")
    assert result.score == 0.2
    assert result.passed is False
    assert result.metadata["missing_points"] == ["x"]


def test_llm_answer_judge_falls_back_when_json_unparseable(base_sample: QAEvalSample):
    from app.evaluation.judges import LLMAnswerJudge

    judge = LLMAnswerJudge(llm_call=lambda prompt: "this is not json at all")
    result = judge.evaluate(base_sample, predicted_answer="x")
    assert result.score == 0.0
    assert result.passed is False
    assert result.metadata["status"] == "parse_error"


def test_llm_answer_judge_clamps_out_of_range_scores(base_sample: QAEvalSample):
    from app.evaluation.judges import LLMAnswerJudge

    judge_high = LLMAnswerJudge(llm_call=lambda p: '{"score": 1.7}')
    assert judge_high.evaluate(base_sample, "x").score == 1.0
    judge_low = LLMAnswerJudge(llm_call=lambda p: '{"score": -0.3}')
    assert judge_low.evaluate(base_sample, "x").score == 0.0


def test_llm_answer_judge_derives_passed_from_threshold_when_missing(base_sample: QAEvalSample):
    from app.evaluation.judges import LLMAnswerJudge

    judge = LLMAnswerJudge(pass_threshold=0.5, llm_call=lambda p: '{"score": 0.6, "reason": "ok"}')
    assert judge.evaluate(base_sample, "x").passed is True

    judge2 = LLMAnswerJudge(pass_threshold=0.5, llm_call=lambda p: '{"score": 0.4, "reason": "weak"}')
    assert judge2.evaluate(base_sample, "x").passed is False


def test_llm_answer_judge_records_llm_error(base_sample: QAEvalSample):
    from app.evaluation.judges import LLMAnswerJudge

    def boom(prompt):
        raise RuntimeError("upstream 502")

    judge = LLMAnswerJudge(llm_call=boom)
    result = judge.evaluate(base_sample, predicted_answer="x")
    assert result.score == 0.0
    assert result.passed is False
    assert result.metadata["status"] == "llm_error"
    assert "502" in result.metadata["error"]


def test_llm_citation_judge_parses_full_payload(base_sample: QAEvalSample):
    from app.evaluation.judges import LLMCitationJudge

    canned = '{"score": 0.75, "passed": true, "reason": "Citations are relevant", "irrelevant_citations": [], "missing_evidence": ["E1"]}'
    judge = LLMCitationJudge(llm_call=lambda prompt: canned)
    citations = [{"paper_id": "paper-1", "section": "Abstract", "score": 0.9}]
    result = judge.evaluate(base_sample, citations=citations, predicted_answer="The paper proposes ...")
    assert result.score == 0.75
    assert result.passed is True
    assert result.metadata["citation_count"] == 1
    assert result.metadata["missing_evidence"] == ["E1"]


def test_llm_citation_judge_handles_empty_citations(base_sample: QAEvalSample):
    from app.evaluation.judges import LLMCitationJudge

    received: dict = {}

    def capture(prompt: str) -> str:
        received["prompt"] = prompt
        return '{"score": 0.0, "passed": false, "reason": "No citations provided"}'

    judge = LLMCitationJudge(llm_call=capture)
    result = judge.evaluate(base_sample, citations=[], predicted_answer="A")
    assert result.score == 0.0
    assert "(无引用)" in received["prompt"]


def test_judge_prompt_builders_produce_expected_keys():
    from app.evaluation.prompts import build_answer_judge_prompt, build_citation_judge_prompt

    ans_prompt = build_answer_judge_prompt(
        question="Q?", expected_answer="E", predicted_answer="P"
    )
    assert "【问题】" in ans_prompt and "【参考答案】" in ans_prompt and "【模型答案】" in ans_prompt
    assert "score" in ans_prompt and "passed" in ans_prompt

    cite_prompt = build_citation_judge_prompt(
        question="Q?",
        predicted_answer="A",
        citations=[{"paper_id": "p1", "section": "Abstract", "score": 0.8}],
        expected_sections=["Abstract", "Method"],
        expected_paper_id="p1",
    )
    assert "p1" in cite_prompt
    assert "Abstract, Method" in cite_prompt


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
