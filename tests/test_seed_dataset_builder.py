import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from app.evaluation.schemas import ComparisonEvalSample, QAEvalSample

REPO_ROOT = Path(__file__).resolve().parents[1]
METADATA_DIR = REPO_ROOT / "app" / "storage" / "metadata"
SCRIPT_PATH = REPO_ROOT / "app" / "evaluation" / "scripts" / "build_seed_dataset.py"
QA_OUTPUT = REPO_ROOT / "app" / "evaluation" / "datasets" / "qa_eval_seed.jsonl"
COMPARISON_OUTPUT = (
    REPO_ROOT / "app" / "evaluation" / "datasets" / "comparison_eval_seed.jsonl"
)
PYTHON_EXECUTABLE = sys.executable


def _read_jsonl(path: Path) -> list[dict]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def test_build_seed_dataset_script_generates_minimal_eval_artifacts(tmp_path: Path):
    # Depends on real parsed papers under app/storage/metadata/, which is
    # gitignored and empty on CI. Skip when no parsed fixtures are present.
    if not METADATA_DIR.exists() or not any(METADATA_DIR.glob("*_parsed.json")):
        pytest.skip("no parsed metadata fixtures under app/storage/metadata/")

    output_dir = tmp_path / "datasets"

    result = subprocess.run(
        [
            PYTHON_EXECUTABLE,
            str(SCRIPT_PATH),
            "--metadata-dir",
            str(METADATA_DIR),
            "--output-dir",
            str(output_dir),
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr

    qa_path = output_dir / "qa_eval_seed.jsonl"
    comparison_path = output_dir / "comparison_eval_seed.jsonl"

    assert qa_path.exists(), "QA dataset file was not generated"
    assert comparison_path.exists(), "Comparison dataset file was not generated"

    qa_rows = _read_jsonl(qa_path)
    comparison_rows = _read_jsonl(comparison_path)

    assert len(qa_rows) >= 4
    assert len(comparison_rows) >= 1

    qa_types = {row["metadata"]["generation_type"] for row in qa_rows}
    assert "abstract" in qa_types
    assert "section" in qa_types

    comparison_sample = ComparisonEvalSample.model_validate(comparison_rows[0])
    assert len(comparison_sample.paper_ids) >= 2
    assert comparison_sample.comparison_aspects

    qa_samples = [QAEvalSample.model_validate(row) for row in qa_rows]
    assert all(sample.supporting_sections for sample in qa_samples)
    assert all(sample.metadata.get("source_pdf") for sample in qa_samples)


def test_generated_seed_dataset_files_are_schema_compatible_and_traceable():
    assert QA_OUTPUT.exists(), "Expected committed QA seed dataset artifact"
    assert (
        COMPARISON_OUTPUT.exists()
    ), "Expected committed comparison seed dataset artifact"

    qa_rows = _read_jsonl(QA_OUTPUT)
    comparison_rows = _read_jsonl(COMPARISON_OUTPUT)

    assert qa_rows, "Committed QA seed dataset is empty"
    assert comparison_rows, "Committed comparison seed dataset is empty"

    qa_samples = [QAEvalSample.model_validate(row) for row in qa_rows]
    comparison_samples = [
        ComparisonEvalSample.model_validate(row) for row in comparison_rows
    ]

    assert any(
        sample.metadata.get("generation_type") == "abstract" for sample in qa_samples
    )
    assert any(
        sample.metadata.get("generation_type") == "section" for sample in qa_samples
    )
    assert all(sample.metadata.get("source_paper_title") for sample in qa_samples)
    assert all(sample.metadata.get("source_pdf") for sample in qa_samples)
    assert all(sample.metadata.get("source_paper_ids") for sample in comparison_samples)
    assert all(sample.supporting_sections for sample in comparison_samples)
