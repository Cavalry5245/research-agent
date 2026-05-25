import json
import os
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.evaluation.schemas import QAEvalSample

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = REPO_ROOT / "app" / "evaluation" / "scripts" / "evaluate_qa.py"
PYTHON_EXECUTABLE = sys.executable


def test_build_seed_qa_predictions_generates_offline_answer_and_citations():
    from app.evaluation.scripts.evaluate_qa import build_seed_qa_predictions

    sample = QAEvalSample(
        sample_id="qa-eval-1",
        question="What is proposed?",
        expected_answer="The paper proposes a grounded QA approach.",
        paper_id="paper-7",
        paper_title="Paper 7",
        supporting_sections=["Abstract", "Method"],
    )

    prediction = build_seed_qa_predictions(sample)

    assert prediction["predicted_answer"] == sample.expected_answer
    assert [citation["section"] for citation in prediction["citations"]] == ["Abstract", "Method"]
    assert all(citation["paper_id"] == "paper-7" for citation in prediction["citations"])


def test_evaluate_qa_sample_runs_answer_and_citation_judges():
    from app.evaluation.judges import RuleBasedAnswerJudge, RuleBasedCitationJudge
    from app.evaluation.scripts.evaluate_qa import evaluate_qa_sample

    sample = QAEvalSample(
        sample_id="qa-eval-2",
        question="Summarize the method.",
        expected_answer="The method uses structured retrieval with grounded citations.",
        paper_id="paper-8",
        paper_title="Paper 8",
        supporting_sections=["Method"],
    )
    prediction = {
        "predicted_answer": "The method uses structured retrieval with grounded citations.",
        "citations": [{"paper_id": "paper-8", "section": "Method", "chunk_id": "paper-8-method-1"}],
    }

    result = evaluate_qa_sample(
        sample=sample,
        prediction=prediction,
        answer_judge=RuleBasedAnswerJudge(),
        citation_judge=RuleBasedCitationJudge(),
        mode="rule_based",
    )

    assert result.sample_id == "qa-eval-2"
    assert result.mode == "rule_based"
    assert result.answer_evaluation.passed is True
    assert result.citation_evaluation.passed is True
    assert result.predicted_answer == prediction["predicted_answer"]
    assert result.citations == prediction["citations"]


def test_summarize_qa_results_aggregates_answer_and_citation_scores():
    from app.evaluation.judges import JudgeResult
    from app.evaluation.scripts.evaluate_qa import QAEvaluationResult, summarize_qa_results

    results = [
        QAEvaluationResult(
            sample_id="qa-1",
            question="q1",
            mode="rule_based",
            predicted_answer="a1",
            citations=[{"paper_id": "paper-1", "section": "Abstract"}],
            answer_evaluation=JudgeResult(
                mode="rule_based",
                score=1.0,
                max_score=1.0,
                passed=True,
                reasons=["full match"],
                metadata={},
            ),
            citation_evaluation=JudgeResult(
                mode="rule_based",
                score=0.5,
                max_score=1.0,
                passed=False,
                reasons=["partial support"],
                metadata={},
            ),
        ),
        QAEvaluationResult(
            sample_id="qa-2",
            question="q2",
            mode="rule_based",
            predicted_answer="a2",
            citations=[],
            answer_evaluation=JudgeResult(
                mode="rule_based",
                score=0.0,
                max_score=1.0,
                passed=False,
                reasons=["miss"],
                metadata={},
            ),
            citation_evaluation=JudgeResult(
                mode="rule_based",
                score=1.0,
                max_score=1.0,
                passed=True,
                reasons=["good support"],
                metadata={},
            ),
        ),
    ]

    summary = summarize_qa_results(results, mode="rule_based")

    assert summary["sample_count"] == 2
    assert summary["evaluation_mode"] == "rule_based"
    assert summary["answer_pass_rate"] == 0.5
    assert summary["citation_pass_rate"] == 0.5
    assert summary["mean_answer_score"] == 0.5
    assert summary["mean_citation_score"] == 0.75


def test_evaluate_qa_dataset_returns_offline_scaffold_results(tmp_path: Path):
    from app.evaluation.scripts.evaluate_qa import evaluate_qa_dataset

    dataset_path = tmp_path / "qa_dataset.jsonl"
    rows = [
        {
            "sample_id": "qa-dataset-1",
            "question": "What is proposed?",
            "expected_answer": "The paper proposes an offline judge scaffold.",
            "paper_id": "paper-a",
            "paper_title": "Paper A",
            "supporting_sections": ["Abstract"],
        },
        {
            "sample_id": "qa-dataset-2",
            "question": "What does the method do?",
            "expected_answer": "The method adds citation-aware evaluation.",
            "paper_id": "paper-b",
            "paper_title": "Paper B",
            "supporting_sections": ["Method"],
        },
    ]
    dataset_path.write_text("\n".join(json.dumps(row) for row in rows), encoding="utf-8")

    payload = evaluate_qa_dataset(dataset_path=dataset_path, mode="rule_based")

    assert payload["dataset"] == str(dataset_path)
    assert payload["summary"]["sample_count"] == 2
    assert payload["summary"]["evaluation_mode"] == "rule_based"
    assert len(payload["results"]) == 2
    assert all(result["answer_evaluation"]["passed"] for result in payload["results"])
    assert all(result["citation_evaluation"]["passed"] for result in payload["results"])


def test_evaluate_qa_script_supports_placeholder_mode(tmp_path: Path):
    dataset_path = tmp_path / "qa_dataset.jsonl"
    dataset_path.write_text(
        json.dumps(
            {
                "sample_id": "qa-script-1",
                "question": "What is proposed?",
                "expected_answer": "A placeholder judge extension point.",
                "paper_id": "paper-c",
                "paper_title": "Paper C",
                "supporting_sections": ["Abstract"],
            }
        )
        + "\n",
        encoding="utf-8",
    )
    report_path = tmp_path / "qa_eval_placeholder.json"

    result = subprocess.run(
        [
            PYTHON_EXECUTABLE,
            str(SCRIPT_PATH),
            "--dataset",
            str(dataset_path),
            "--mode",
            "placeholder_llm",
            "--output",
            str(report_path),
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(report_path.read_text(encoding="utf-8"))
    assert payload["summary"]["evaluation_mode"] == "placeholder_llm"
    assert payload["results"][0]["answer_evaluation"]["metadata"]["status"] == "not_implemented"
    assert payload["results"][0]["citation_evaluation"]["metadata"]["status"] == "not_implemented"


def test_build_live_qa_predictions_uses_answer_question(monkeypatch):
    from app.evaluation.scripts import evaluate_qa as eq

    captured: dict = {}

    def fake_answer_question(question, vector_store, embedding_client, llm_client, paper_id=None, top_k=5, **kwargs):
        captured["question"] = question
        captured["paper_id"] = paper_id
        captured["top_k"] = top_k
        return {
            "question": question,
            "answer": "Live answer about retrieval.",
            "sources": [
                {"paper_id": paper_id, "section": "Abstract", "chunk_id": "c1", "title": "T", "score": 0.9},
                {"paper_id": paper_id, "section": "Method", "chunk_id": "c2", "title": "T", "score": 0.8},
            ],
        }

    monkeypatch.setattr("app.services.paper_qa.answer_question", fake_answer_question)

    sample = QAEvalSample(
        sample_id="qa-live-1",
        question="What is the contribution?",
        expected_answer="A retrieval-grounded QA pipeline.",
        paper_id="paper-live-1",
        paper_title="Live Paper",
        supporting_sections=["Abstract"],
    )

    prediction = eq.build_live_qa_predictions(
        sample,
        vector_store=object(),
        embedding_client=object(),
        llm_client=object(),
        top_k=3,
    )

    assert captured == {"question": "What is the contribution?", "paper_id": "paper-live-1", "top_k": 3}
    assert prediction["predicted_answer"] == "Live answer about retrieval."
    assert [c["section"] for c in prediction["citations"]] == ["Abstract", "Method"]
    assert prediction["citations"][0]["score"] == 0.9


def test_build_live_qa_predictions_returns_empty_on_failure(monkeypatch):
    from app.evaluation.scripts import evaluate_qa as eq

    def fake_answer_question(*args, **kwargs):
        raise RuntimeError("LLM unavailable")

    monkeypatch.setattr("app.services.paper_qa.answer_question", fake_answer_question)

    sample = QAEvalSample(
        sample_id="qa-live-fail",
        question="?",
        expected_answer="expected",
        paper_id="p",
        paper_title="T",
        supporting_sections=["Abstract"],
    )

    prediction = eq.build_live_qa_predictions(
        sample,
        vector_store=object(),
        embedding_client=object(),
        llm_client=object(),
    )

    assert prediction == {"predicted_answer": "", "citations": []}


def test_evaluate_qa_dataset_live_pipeline_flag(monkeypatch, tmp_path: Path):
    from app.evaluation.scripts import evaluate_qa as eq

    monkeypatch.setattr(eq, "_build_live_pipeline_clients", lambda: (object(), object(), object()))
    monkeypatch.setattr(
        eq,
        "build_live_qa_predictions",
        lambda sample, vector_store, embedding_client, llm_client, top_k=5, **kwargs: {
            "predicted_answer": "Live: " + sample.expected_answer,
            "citations": [
                {"paper_id": sample.paper_id, "section": "Abstract", "chunk_id": "c", "title": "T"}
            ],
        },
    )

    dataset_path = tmp_path / "qa.jsonl"
    dataset_path.write_text(
        json.dumps(
            {
                "sample_id": "qa-live-ds-1",
                "question": "Q?",
                "expected_answer": "A.",
                "paper_id": "p",
                "paper_title": "T",
                "supporting_sections": ["Abstract"],
            }
        )
        + "\n",
        encoding="utf-8",
    )

    payload = eq.evaluate_qa_dataset(dataset_path=dataset_path, use_live_pipeline=True)

    assert payload["pipeline"] == "live"
    assert payload["results"][0]["predicted_answer"].startswith("Live: ")
