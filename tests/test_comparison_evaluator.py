import json
import subprocess
import sys
from pathlib import Path

import pytest

from app.evaluation.reporting import (
    build_comparison_report_markdown,
    build_comparison_report_payload,
)
from app.evaluation.scripts.evaluate_comparison import (
    evaluate_comparison_dataset,
    generate_live_compare_predictions,
    inject_live_compare_predictions,
)
from app.schemas import (
    CompareBatchRunResult,
    CompareBatchSampleResult,
    PaperComparisonResult,
    PaperStructuredSummary,
)
from app.services.paper_compare import compare_papers_batch

SCRIPT_PATH = Path("app/evaluation/scripts/evaluate_comparison.py")


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.write_text(
        "\n".join(json.dumps(row, ensure_ascii=False) for row in rows) + "\n",
        encoding="utf-8",
    )


def test_evaluate_comparison_dataset_reports_completeness_and_balance(tmp_path: Path):
    dataset_path = tmp_path / "comparison_eval_seed.jsonl"
    _write_jsonl(
        dataset_path,
        [
            {
                "sample_id": "cmp-001",
                "question": "比较两篇论文的方法、数据集和局限性。",
                "paper_ids": ["paper_a", "paper_b"],
                "paper_titles": ["Paper A", "Paper B"],
                "expected_summary": "Paper A 偏分类，Paper B 偏检测。",
                "comparison_aspects": ["method", "dataset", "limitations"],
                "supporting_sections": {
                    "paper_a": ["Method", "Experiments"],
                    "paper_b": ["Method", "Results"],
                },
                "metadata": {},
            }
        ],
    )

    report = evaluate_comparison_dataset(dataset_path)

    assert report["summary"]["sample_count"] == 1
    assert report["summary"]["mean_completeness"] == 1.0
    assert report["summary"]["mean_evidence_completeness"] == 1.0
    assert report["summary"]["mean_paper_balance"] == 1.0

    result = report["results"][0]
    assert result["missing_aspects"] == []
    assert result["aspects_with_missing_evidence"] == []
    assert result["paper_coverage"]["paper_a"] is True
    assert result["paper_coverage"]["paper_b"] is True


def test_evaluate_comparison_dataset_flags_missing_aspects_and_evidence(tmp_path: Path):
    dataset_path = tmp_path / "comparison_eval_seed.jsonl"
    _write_jsonl(
        dataset_path,
        [
            {
                "sample_id": "cmp-002",
                "question": "比较两篇论文的方法、数据集和局限性。",
                "paper_ids": ["paper_a", "paper_b"],
                "paper_titles": ["Paper A", "Paper B"],
                "expected_summary": "Paper A 偏分类，Paper B 偏检测。",
                "comparison_aspects": ["method", "dataset", "limitations"],
                "supporting_sections": {
                    "paper_a": ["Method"],
                    "paper_b": ["Results"],
                },
                "metadata": {
                    "predicted_comparison": {
                        "overview": "只覆盖了部分维度。",
                        "aspects": [
                            {
                                "name": "method",
                                "summary": "A 用 Transformer，B 用 CNN。",
                                "per_paper": {
                                    "paper_a": "Transformer",
                                    "paper_b": "未明确说明",
                                },
                                "key_differences": [],
                                "evidence": [],
                            },
                            {
                                "name": "dataset",
                                "summary": "只说明了 Paper A 的数据集。",
                                "per_paper": {
                                    "paper_a": "CIFAR-10",
                                    "paper_b": "未明确说明",
                                },
                                "key_differences": [],
                                "evidence": [
                                    {
                                        "paper_id": "paper_a",
                                        "paper_title": "Paper A",
                                        "section": "Experiments",
                                        "snippet": "Evaluated on CIFAR-10.",
                                    }
                                ],
                            },
                        ],
                        "markdown": "# stub",
                    }
                },
            }
        ],
    )

    report = evaluate_comparison_dataset(dataset_path)
    result = report["results"][0]

    assert result["missing_aspects"] == ["limitations"]
    assert result["aspects_with_missing_evidence"] == ["method", "limitations"]
    assert result["paper_coverage"]["paper_b"] is False
    assert result["completeness"] == 2 / 3
    assert result["evidence_completeness"] == 1 / 3
    assert result["paper_balance"] == 0.5


def test_evaluate_comparison_dataset_distinguishes_missing_evidence_from_section_mismatch(
    tmp_path: Path,
):
    dataset_path = tmp_path / "comparison_eval_seed.jsonl"
    _write_jsonl(
        dataset_path,
        [
            {
                "sample_id": "cmp-002b",
                "question": "比较两篇论文的方法和数据集。",
                "paper_ids": ["paper_a", "paper_b"],
                "paper_titles": ["Paper A", "Paper B"],
                "expected_summary": "Paper A 偏分类，Paper B 偏检测。",
                "comparison_aspects": ["method", "dataset"],
                "supporting_sections": {
                    "paper_a": ["Method", "Experiments"],
                    "paper_b": ["Method", "Experiments"],
                },
                "metadata": {
                    "predicted_comparison": {
                        "overview": "两个维度都已覆盖，但数据集证据 section 错位。",
                        "aspects": [
                            {
                                "name": "method",
                                "summary": "A 用 Transformer，B 用 CNN。",
                                "per_paper": {
                                    "paper_a": "Transformer",
                                    "paper_b": "CNN",
                                },
                                "key_differences": [],
                                "evidence": [
                                    {
                                        "paper_id": "paper_a",
                                        "paper_title": "Paper A",
                                        "section": "Method",
                                        "snippet": "We adopt a Transformer encoder.",
                                    },
                                    {
                                        "paper_id": "paper_b",
                                        "paper_title": "Paper B",
                                        "section": "Method",
                                        "snippet": "Our backbone is a CNN.",
                                    },
                                ],
                            },
                            {
                                "name": "dataset",
                                "summary": "A 使用 CIFAR-10，B 使用 ImageNet。",
                                "per_paper": {
                                    "paper_a": "CIFAR-10",
                                    "paper_b": "ImageNet",
                                },
                                "key_differences": [],
                                "evidence": [
                                    {
                                        "paper_id": "paper_a",
                                        "paper_title": "Paper A",
                                        "section": "Conclusion",
                                        "snippet": "CIFAR-10 leads to strong results.",
                                    },
                                    {
                                        "paper_id": "paper_b",
                                        "paper_title": "Paper B",
                                        "section": "Conclusion",
                                        "snippet": "ImageNet is discussed in the conclusion.",
                                    },
                                ],
                            },
                        ],
                        "markdown": "# stub",
                    }
                },
            }
        ],
    )

    report = evaluate_comparison_dataset(dataset_path)
    result = report["results"][0]

    assert result["aspects_with_missing_evidence"] == []
    assert result["evidence_quality_issues"] == []
    assert result["section_alignment_issues"] == ["dataset"]
    assert result["section_alignment"] == 0.5
    assert result["evidence_quality"] == 1.0
    assert report["summary"]["mean_section_alignment"] == 0.5


def test_evaluate_comparison_dataset_flags_semantic_evidence_mismatch_separately_from_section_alignment(
    tmp_path: Path,
):
    dataset_path = tmp_path / "comparison_eval_seed.jsonl"
    _write_jsonl(
        dataset_path,
        [
            {
                "sample_id": "cmp-002b-semantic",
                "question": "比较两篇论文的数据集。",
                "paper_ids": ["paper_a", "paper_b"],
                "paper_titles": ["Paper A", "Paper B"],
                "expected_summary": "两篇论文使用不同数据集。",
                "comparison_aspects": ["dataset"],
                "supporting_sections": {
                    "paper_a": ["Experiments"],
                    "paper_b": ["Experiments"],
                },
                "metadata": {
                    "predicted_comparison": {
                        "overview": "数据集维度已覆盖，但证据片段语义上在讲方法。",
                        "aspects": [
                            {
                                "name": "dataset",
                                "summary": "A 使用 CIFAR-10，B 使用 ImageNet。",
                                "per_paper": {
                                    "paper_a": "CIFAR-10",
                                    "paper_b": "ImageNet",
                                },
                                "key_differences": [],
                                "evidence": [
                                    {
                                        "paper_id": "paper_a",
                                        "paper_title": "Paper A",
                                        "section": "Experiments",
                                        "snippet": "We use a Transformer encoder for representation learning.",
                                    },
                                    {
                                        "paper_id": "paper_b",
                                        "paper_title": "Paper B",
                                        "section": "Experiments",
                                        "snippet": "Our CNN backbone improves optimization stability.",
                                    },
                                ],
                            }
                        ],
                        "markdown": "# stub",
                    }
                },
            }
        ],
    )

    report = evaluate_comparison_dataset(dataset_path)
    result = report["results"][0]

    assert result["aspects_with_missing_evidence"] == []
    assert result["section_alignment_issues"] == []
    assert result["paper_alignment_issues"] == {}
    assert result["section_alignment"] == 1.0
    assert result["evidence_quality_issues"] == ["dataset"]
    assert result["evidence_quality"] == 0.0
    assert report["summary"]["mean_evidence_quality"] == 0.0


def test_evaluate_comparison_dataset_tracks_partial_section_alignment_per_paper(
    tmp_path: Path,
):
    dataset_path = tmp_path / "comparison_eval_seed.jsonl"
    _write_jsonl(
        dataset_path,
        [
            {
                "sample_id": "cmp-002c",
                "question": "比较两篇论文的数据集。",
                "paper_ids": ["paper_a", "paper_b"],
                "paper_titles": ["Paper A", "Paper B"],
                "expected_summary": "两篇论文使用不同数据集。",
                "comparison_aspects": ["dataset"],
                "supporting_sections": {
                    "paper_a": ["Experiments"],
                    "paper_b": ["Results"],
                },
                "metadata": {
                    "predicted_comparison": {
                        "overview": "数据集已覆盖，但只对齐了其中一篇论文的证据 section。",
                        "aspects": [
                            {
                                "name": "dataset",
                                "summary": "A 使用 CIFAR-10，B 使用 ImageNet。",
                                "per_paper": {
                                    "paper_a": "CIFAR-10",
                                    "paper_b": "ImageNet",
                                },
                                "key_differences": [],
                                "evidence": [
                                    {
                                        "paper_id": "paper_a",
                                        "paper_title": "Paper A",
                                        "section": "Experiments",
                                        "snippet": "We evaluate on CIFAR-10.",
                                    },
                                    {
                                        "paper_id": "paper_b",
                                        "paper_title": "Paper B",
                                        "section": "Conclusion",
                                        "snippet": "ImageNet is discussed in the conclusion.",
                                    },
                                ],
                            }
                        ],
                        "markdown": "# stub",
                    }
                },
            }
        ],
    )

    report = evaluate_comparison_dataset(dataset_path)
    result = report["results"][0]

    assert result["aspects_with_missing_evidence"] == []
    assert result["section_alignment_issues"] == ["dataset"]
    assert result["section_alignment"] == 0.5
    assert result["paper_alignment"]["paper_a"] == 1.0
    assert result["paper_alignment"]["paper_b"] == 0.0
    assert result["paper_alignment_issues"] == {"dataset": ["paper_b"]}
    assert report["summary"]["mean_section_alignment"] == 0.5


def test_build_comparison_report_markdown_includes_semantic_evidence_mismatch_details():
    payload = build_comparison_report_payload(
        {
            "summary": {
                "sample_count": 1,
                "mean_completeness": 1.0,
                "mean_evidence_completeness": 1.0,
                "mean_evidence_quality": 0.0,
                "mean_section_alignment": 1.0,
                "mean_paper_balance": 1.0,
            },
            "results": [
                {
                    "sample_id": "cmp-semantic-001",
                    "question": "比较两篇论文的数据集",
                    "expected_aspects": ["dataset"],
                    "predicted_aspects": ["dataset"],
                    "missing_aspects": [],
                    "aspects_with_missing_evidence": [],
                    "paper_coverage": {"paper_a": True, "paper_b": True},
                    "paper_alignment": {"paper_a": 1.0, "paper_b": 1.0},
                    "paper_alignment_issues": {},
                    "section_alignment_issues": [],
                    "evidence_quality_issues": ["dataset"],
                    "completeness": 1.0,
                    "evidence_completeness": 1.0,
                    "evidence_quality": 0.0,
                    "section_alignment": 1.0,
                    "paper_balance": 1.0,
                    "comparison_source": "predicted_comparison",
                    "uses_structured_summaries": True,
                }
            ],
        }
    )

    markdown = build_comparison_report_markdown(payload)

    assert "- Mean evidence quality: 0.000" in markdown
    assert "- Mean section alignment: 1.000" in markdown
    assert "### cmp-semantic-001" in markdown
    assert "- Evidence quality issues: dataset" in markdown
    assert "- Section alignment issues: 无" in markdown
    assert "- Paper alignment: paper_a=1.000, paper_b=1.000" in markdown
    assert "- Paper alignment issues: 无" in markdown


def test_evaluate_comparison_script_generates_report_files(tmp_path: Path):
    dataset_path = tmp_path / "comparison_eval_seed.jsonl"
    output_path = tmp_path / "comparison_eval_report.json"
    markdown_path = tmp_path / "comparison_eval_report.md"
    compare_output_path = tmp_path / "comparison_eval_predictions.json"
    _write_jsonl(
        dataset_path,
        [
            {
                "sample_id": "cmp-003",
                "question": "比较两篇论文的核心方法。",
                "paper_ids": ["paper_a", "paper_b"],
                "paper_titles": ["Paper A", "Paper B"],
                "expected_summary": "A 偏分类，B 偏检测。",
                "comparison_aspects": ["method"],
                "supporting_sections": {"paper_a": ["Method"], "paper_b": ["Method"]},
                "metadata": {},
            }
        ],
    )

    completed = subprocess.run(
        [
            sys.executable,
            str(SCRIPT_PATH),
            "--dataset",
            str(dataset_path),
            "--output",
            str(output_path),
            "--markdown-output",
            str(markdown_path),
        ],
        capture_output=True,
        text=True,
        check=True,
    )

    assert "Generated comparison evaluation report" in completed.stdout
    report = json.loads(output_path.read_text(encoding="utf-8"))
    markdown = markdown_path.read_text(encoding="utf-8")
    assert report["summary"]["sample_count"] == 1
    assert "Structured Comparison Evaluation Report" in markdown
    assert not compare_output_path.exists()


def test_cli_generate_live_compare_with_real_metadata_generates_reports(tmp_path: Path):
    source_dataset = Path("app/evaluation/datasets/comparison_eval_seed.jsonl")
    dataset_rows = [
        json.loads(line)
        for line in source_dataset.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    metadata_dir = Path("app/storage/metadata")

    compatible_rows = [
        row
        for row in dataset_rows
        if all(
            (metadata_dir / f"{paper_id}_parsed.json").exists()
            for paper_id in row.get("paper_ids", [])
        )
    ]
    if not compatible_rows:
        pytest.skip(
            "No real parsed metadata fixtures in app/storage/metadata "
            "(gitignored); requires local paper data"
        )

    dataset_path = tmp_path / "comparison_eval_seed_real_metadata.jsonl"
    compare_output_path = tmp_path / "comparison_eval_predictions.json"
    report_output_path = tmp_path / "comparison_eval_seed_report.json"
    markdown_output_path = tmp_path / "comparison_eval_seed_report.md"
    _write_jsonl(dataset_path, [compatible_rows[0]])

    command = [
        sys.executable,
        str(SCRIPT_PATH),
        "--dataset",
        str(dataset_path),
        "--compare-output",
        str(compare_output_path),
        "--output",
        str(report_output_path),
        "--markdown-output",
        str(markdown_output_path),
        "--metadata-dir",
        str(metadata_dir),
    ]
    completed = subprocess.run(command, capture_output=True, text=True, check=True)

    assert "Generated comparison evaluation report" in completed.stdout
    assert report_output_path.exists()
    assert markdown_output_path.exists()
    assert not compare_output_path.exists()

    report = json.loads(report_output_path.read_text(encoding="utf-8"))
    markdown = markdown_output_path.read_text(encoding="utf-8")
    assert report["summary"]["sample_count"] == 1
    assert report["results"][0]["comparison_source"] == "deterministic_stub"
    assert "Structured Comparison Evaluation Report" in markdown


def test_cli_generate_live_compare_with_real_metadata_and_stubbed_llm_generates_live_report(
    tmp_path: Path,
):
    source_dataset = Path("app/evaluation/datasets/comparison_eval_seed.jsonl")
    dataset_rows = [
        json.loads(line)
        for line in source_dataset.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    metadata_dir = Path("app/storage/metadata")

    compatible_rows = [
        row
        for row in dataset_rows
        if all(
            (metadata_dir / f"{paper_id}_parsed.json").exists()
            for paper_id in row.get("paper_ids", [])
        )
    ]
    if not compatible_rows:
        pytest.skip(
            "No real parsed metadata fixtures in app/storage/metadata "
            "(gitignored); requires local paper data"
        )

    dataset_path = tmp_path / "comparison_eval_seed_live_compare.jsonl"
    compare_output_path = tmp_path / "comparison_eval_predictions.json"
    report_output_path = tmp_path / "comparison_eval_seed_report.json"
    markdown_output_path = tmp_path / "comparison_eval_seed_report.md"
    row = compatible_rows[0]
    _write_jsonl(dataset_path, [row])

    paper_ids = row["paper_ids"]
    paper_titles = row["paper_titles"]

    original_extract = compare_papers_batch.__globals__["extract_paper_summaries"]
    original_compare = compare_papers_batch.__globals__["compare_papers"]

    compare_papers_batch.__globals__["extract_paper_summaries"] = (
        lambda paper_ids, metadata_dir, llm_client=None: {
            paper_ids[0]: PaperStructuredSummary(
                paper_id=paper_ids[0],
                paper_title=paper_titles[0],
                research_problem="研究问题A",
                method="方法A",
                backbone="骨干A",
                dataset="数据集A",
                metrics="指标A",
                strengths="优势A",
                limitations="局限A",
                scenarios="场景A",
                evidence=[],
            ),
            paper_ids[1]: PaperStructuredSummary(
                paper_id=paper_ids[1],
                paper_title=paper_titles[1],
                research_problem="研究问题B",
                method="方法B",
                backbone="骨干B",
                dataset="数据集B",
                metrics="指标B",
                strengths="优势B",
                limitations="局限B",
                scenarios="场景B",
                evidence=[],
            ),
        }
    )
    compare_papers_batch.__globals__["compare_papers"] = (
        lambda paper_ids, metadata_dir, llm_client=None: PaperComparisonResult.model_validate(
            {
                "overview": "已生成 live compare。",
                "aspects": [
                    {
                        "name": "dataset",
                        "summary": "两篇论文使用不同数据集。",
                        "per_paper": {
                            paper_ids[0]: "数据集A",
                            paper_ids[1]: "数据集B",
                        },
                        "key_differences": ["数据集不同"],
                        "evidence": [
                            {
                                "paper_id": paper_ids[0],
                                "paper_title": paper_titles[0],
                                "section": row["supporting_sections"][paper_ids[0]][0],
                                "snippet": f"{paper_titles[0]} dataset evidence",
                            },
                            {
                                "paper_id": paper_ids[1],
                                "paper_title": paper_titles[1],
                                "section": row["supporting_sections"][paper_ids[1]][0],
                                "snippet": f"{paper_titles[1]} dataset evidence",
                            },
                        ],
                    }
                ],
                "markdown": "# compare output",
                "structured_summaries": {
                    paper_ids[0]: {
                        "paper_id": paper_ids[0],
                        "paper_title": paper_titles[0],
                        "research_problem": "研究问题A",
                        "method": "方法A",
                        "backbone": "骨干A",
                        "dataset": "数据集A",
                        "metrics": "指标A",
                        "strengths": "优势A",
                        "limitations": "局限A",
                        "scenarios": "场景A",
                        "evidence": [],
                    },
                    paper_ids[1]: {
                        "paper_id": paper_ids[1],
                        "paper_title": paper_titles[1],
                        "research_problem": "研究问题B",
                        "method": "方法B",
                        "backbone": "骨干B",
                        "dataset": "数据集B",
                        "metrics": "指标B",
                        "strengths": "优势B",
                        "limitations": "局限B",
                        "scenarios": "场景B",
                        "evidence": [],
                    },
                },
            }
        )
    )

    try:
        result = generate_live_compare_predictions(
            dataset_path=dataset_path,
            metadata_dir=metadata_dir,
            output_path=compare_output_path,
        )
    finally:
        compare_papers_batch.__globals__["extract_paper_summaries"] = original_extract
        compare_papers_batch.__globals__["compare_papers"] = original_compare

    updated_rows = inject_live_compare_predictions(dataset_path, compare_output_path)
    report = evaluate_comparison_dataset(dataset_path)
    report_output_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    markdown_payload = build_comparison_report_payload(report)
    markdown_output_path.write_text(
        build_comparison_report_markdown(markdown_payload), encoding="utf-8"
    )

    assert result.total_samples == 1
    assert (
        updated_rows[0]["metadata"]["predicted_comparison"]["overview"]
        == "已生成 live compare。"
    )
    assert report["summary"]["sample_count"] == 1
    assert report["results"][0]["comparison_source"] == "predicted_comparison"
    assert report["results"][0]["uses_structured_summaries"] is True
    compare_payload = json.loads(compare_output_path.read_text(encoding="utf-8"))
    assert (
        compare_payload["results"][0]["comparison"]["structured_summaries"][
            paper_ids[0]
        ]["dataset"]
        == "数据集A"
    )
    assert "Structured Comparison Evaluation Report" in markdown_output_path.read_text(
        encoding="utf-8"
    )


def test_cli_generate_live_compare_success_subprocess_with_injection_seam(
    tmp_path: Path,
):
    source_dataset = Path("app/evaluation/datasets/comparison_eval_seed.jsonl")
    dataset_rows = [
        json.loads(line)
        for line in source_dataset.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    metadata_dir = Path("app/storage/metadata")
    compatible_rows = [
        row
        for row in dataset_rows
        if all(
            (metadata_dir / f"{paper_id}_parsed.json").exists()
            for paper_id in row.get("paper_ids", [])
        )
    ]
    if not compatible_rows:
        pytest.skip(
            "No real parsed metadata fixtures in app/storage/metadata "
            "(gitignored); requires local paper data"
        )

    row = compatible_rows[0]
    dataset_path = tmp_path / "comparison_eval_seed_live_compare_subprocess.jsonl"
    compare_output_path = tmp_path / "comparison_eval_predictions.json"
    report_output_path = tmp_path / "comparison_eval_seed_report.json"
    markdown_output_path = tmp_path / "comparison_eval_seed_report.md"
    stub_script_path = tmp_path / "stub_compare_batch.py"
    _write_jsonl(dataset_path, [row])

    stub_script_path.write_text(
        """
import json
import sys
from pathlib import Path

REPO_ROOT = Path(r"/home/chase/projects/ResearchAgent")
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from app.schemas import CompareBatchRunResult, CompareBatchSampleResult, PaperComparisonResult


def main() -> None:
    dataset_path = Path(sys.argv[1])
    output_path = Path(sys.argv[2])
    dataset_rows = [
        json.loads(line)
        for line in dataset_path.read_text(encoding=\"utf-8\").splitlines()
        if line.strip()
    ]
    row = dataset_rows[0]
    paper_ids = row[\"paper_ids\"]
    paper_titles = row[\"paper_titles\"]
    comparison = PaperComparisonResult.model_validate(
        {
            \"overview\": \"通过子进程注入 seam 生成 live compare。\",
            \"aspects\": [
                {
                    \"name\": row[\"comparison_aspects\"][0],
                    \"summary\": \"已通过外部 stub compare 生成结构化对比。\",
                    \"per_paper\": {
                        paper_ids[0]: \"覆盖A\",
                        paper_ids[1]: \"覆盖B\",
                    },
                    \"key_differences\": [\"存在差异\"],
                    \"evidence\": [
                        {
                            \"paper_id\": paper_ids[0],
                            \"paper_title\": paper_titles[0],
                            \"section\": row[\"supporting_sections\"][paper_ids[0]][0],
                            \"snippet\": \"paper A evidence\",
                        },
                        {
                            \"paper_id\": paper_ids[1],
                            \"paper_title\": paper_titles[1],
                            \"section\": row[\"supporting_sections\"][paper_ids[1]][0],
                            \"snippet\": \"paper B evidence\",
                        },
                    ],
                }
            ],
            \"markdown\": \"# live compare output\",
            \"structured_summaries\": {
                paper_ids[0]: {
                    \"paper_id\": paper_ids[0],
                    \"paper_title\": paper_titles[0],
                    \"research_problem\": \"问题A\",
                    \"method\": \"方法A\",
                    \"backbone\": \"骨干A\",
                    \"dataset\": \"数据集A\",
                    \"metrics\": \"指标A\",
                    \"strengths\": \"优势A\",
                    \"limitations\": \"局限A\",
                    \"scenarios\": \"场景A\",
                    \"evidence\": [],
                },
                paper_ids[1]: {
                    \"paper_id\": paper_ids[1],
                    \"paper_title\": paper_titles[1],
                    \"research_problem\": \"问题B\",
                    \"method\": \"方法B\",
                    \"backbone\": \"骨干B\",
                    \"dataset\": \"数据集B\",
                    \"metrics\": \"指标B\",
                    \"strengths\": \"优势B\",
                    \"limitations\": \"局限B\",
                    \"scenarios\": \"场景B\",
                    \"evidence\": [],
                },
            },
        }
    )
    result = CompareBatchRunResult(
        dataset_path=str(dataset_path),
        total_samples=1,
        generated_at=\"2026-05-12T12:20:00Z\",
        results=[
            CompareBatchSampleResult(
                sample_id=row[\"sample_id\"],
                question=row[\"question\"],
                paper_ids=paper_ids,
                comparison=comparison,
            )
        ],
    )
    output_path.write_text(result.model_dump_json(indent=2), encoding=\"utf-8\")


if __name__ == \"__main__\":
    main()
""".strip() + "\n",
        encoding="utf-8",
    )

    command = [
        sys.executable,
        str(SCRIPT_PATH),
        "--dataset",
        str(dataset_path),
        "--compare-output",
        str(compare_output_path),
        "--output",
        str(report_output_path),
        "--markdown-output",
        str(markdown_output_path),
        "--metadata-dir",
        str(metadata_dir),
        "--generate-live-compare",
        "--compare-batch-script",
        str(stub_script_path),
    ]
    completed = subprocess.run(command, capture_output=True, text=True)

    assert (
        completed.returncode == 0
    ), f"STDOUT:\n{completed.stdout}\nSTDERR:\n{completed.stderr}"
    report = json.loads(report_output_path.read_text(encoding="utf-8"))
    compare_payload = json.loads(compare_output_path.read_text(encoding="utf-8"))
    markdown = markdown_output_path.read_text(encoding="utf-8")

    assert "Generated comparison evaluation report" in completed.stdout
    assert "Generated comparison evaluation markdown" in completed.stdout
    assert (
        f"Generated live comparison payloads: {compare_output_path} (1 samples)"
        in completed.stdout
    )
    assert '"sample_count": 1' in completed.stdout
    assert report["results"][0]["comparison_source"] == "predicted_comparison"
    assert report["results"][0]["uses_structured_summaries"] is True
    assert (
        compare_payload["results"][0]["comparison"]["structured_summaries"][
            row["paper_ids"][0]
        ]["dataset"]
        == "数据集A"
    )
    assert "Structured Comparison Evaluation Report" in markdown


def test_cli_generate_live_compare_surfaces_compare_stage_invalid_json_clearly(
    tmp_path: Path,
):
    source_dataset = Path("app/evaluation/datasets/comparison_eval_seed.jsonl")
    dataset_rows = [
        json.loads(line)
        for line in source_dataset.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    metadata_dir = Path("app/storage/metadata")
    compatible_rows = [
        row
        for row in dataset_rows
        if all(
            (metadata_dir / f"{paper_id}_parsed.json").exists()
            for paper_id in row.get("paper_ids", [])
        )
    ]
    if not compatible_rows:
        pytest.skip(
            "No real parsed metadata fixtures in app/storage/metadata "
            "(gitignored); requires local paper data"
        )

    row = compatible_rows[0]
    dataset_path = tmp_path / "comparison_eval_seed_invalid_json.jsonl"
    compare_output_path = tmp_path / "comparison_eval_predictions_invalid_json.json"
    report_output_path = tmp_path / "comparison_eval_seed_invalid_json_report.json"
    markdown_output_path = tmp_path / "comparison_eval_seed_invalid_json_report.md"
    stub_script_path = tmp_path / "stub_compare_batch_invalid_json.py"
    _write_jsonl(dataset_path, [row])

    stub_script_path.write_text(
        """
from pathlib import Path
import sys


def main() -> None:
    output_path = Path(sys.argv[2])
    output_path.write_text("{this is not valid json", encoding="utf-8")
    print("wrote invalid compare payload")


if __name__ == "__main__":
    main()
""".strip() + "\n",
        encoding="utf-8",
    )

    command = [
        sys.executable,
        str(SCRIPT_PATH),
        "--dataset",
        str(dataset_path),
        "--compare-output",
        str(compare_output_path),
        "--output",
        str(report_output_path),
        "--markdown-output",
        str(markdown_output_path),
        "--metadata-dir",
        str(metadata_dir),
        "--generate-live-compare",
        "--compare-batch-script",
        str(stub_script_path),
    ]
    result = subprocess.run(command, capture_output=True, text=True)

    assert result.returncode != 0
    assert "wrote invalid compare payload" in result.stdout
    assert "1 validation error for CompareBatchRunResult" in result.stderr
    assert "Invalid JSON" in result.stderr
    assert "论文解析结果不存在" not in result.stderr
    assert "结构化对比结果解析失败" not in result.stderr


def test_cli_generate_live_compare_helper_failure_surfaces_stdout_stderr_and_exit_code(
    tmp_path: Path,
):
    source_dataset = Path("app/evaluation/datasets/comparison_eval_seed.jsonl")
    dataset_rows = [
        json.loads(line)
        for line in source_dataset.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    metadata_dir = Path("app/storage/metadata")
    compatible_rows = [
        row
        for row in dataset_rows
        if all(
            (metadata_dir / f"{paper_id}_parsed.json").exists()
            for paper_id in row.get("paper_ids", [])
        )
    ]
    if not compatible_rows:
        pytest.skip(
            "No real parsed metadata fixtures in app/storage/metadata "
            "(gitignored); requires local paper data"
        )

    row = compatible_rows[0]
    dataset_path = tmp_path / "comparison_eval_seed_helper_failure.jsonl"
    compare_output_path = tmp_path / "comparison_eval_predictions_helper_failure.json"
    report_output_path = tmp_path / "comparison_eval_seed_helper_failure_report.json"
    markdown_output_path = tmp_path / "comparison_eval_seed_helper_failure_report.md"
    stub_script_path = tmp_path / "stub_compare_batch_failure.py"
    _write_jsonl(dataset_path, [row])

    stub_script_path.write_text(
        """
import sys


def main() -> None:
    print("helper stdout before failure")
    print("helper stderr before failure", file=sys.stderr)
    raise SystemExit(7)


if __name__ == "__main__":
    main()
""".strip() + "\n",
        encoding="utf-8",
    )

    command = [
        sys.executable,
        str(SCRIPT_PATH),
        "--dataset",
        str(dataset_path),
        "--compare-output",
        str(compare_output_path),
        "--output",
        str(report_output_path),
        "--markdown-output",
        str(markdown_output_path),
        "--metadata-dir",
        str(metadata_dir),
        "--generate-live-compare",
        "--compare-batch-script",
        str(stub_script_path),
    ]
    result = subprocess.run(command, capture_output=True, text=True)

    assert result.returncode != 0
    assert "helper stdout before failure" in result.stdout
    assert "helper stderr before failure" in result.stderr
    assert "compare batch helper failed with exit code 7" in result.stderr
    assert "STDOUT:" in result.stderr
    assert "STDERR:" in result.stderr
    assert not compare_output_path.exists()
    assert not report_output_path.exists()
    assert not markdown_output_path.exists()


def test_cli_generate_live_compare_rejects_partial_batch_payload_clearly(
    tmp_path: Path,
):
    dataset_path = tmp_path / "comparison_eval_seed_partial.jsonl"
    compare_output_path = tmp_path / "comparison_eval_predictions_partial.json"
    _write_jsonl(
        dataset_path,
        [
            {
                "sample_id": "cmp-live-partial-001",
                "question": "比较第一组论文的方法。",
                "paper_ids": ["paper_a", "paper_b"],
                "paper_titles": ["Paper A", "Paper B"],
                "expected_summary": "A 与 B 方法不同。",
                "comparison_aspects": ["method"],
                "supporting_sections": {"paper_a": ["Method"], "paper_b": ["Method"]},
                "metadata": {},
            },
            {
                "sample_id": "cmp-live-partial-002",
                "question": "比较第二组论文的方法。",
                "paper_ids": ["paper_c", "paper_d"],
                "paper_titles": ["Paper C", "Paper D"],
                "expected_summary": "C 与 D 方法不同。",
                "comparison_aspects": ["method"],
                "supporting_sections": {"paper_c": ["Method"], "paper_d": ["Method"]},
                "metadata": {},
            },
        ],
    )
    compare_output_path.write_text(
        json.dumps(
            {
                "dataset_path": str(dataset_path),
                "total_samples": 1,
                "generated_at": "2026-05-12T11:35:00Z",
                "results": [
                    {
                        "sample_id": "cmp-live-partial-001",
                        "question": "比较第一组论文的方法。",
                        "paper_ids": ["paper_a", "paper_b"],
                        "comparison": {
                            "overview": "只生成了第一条样本的 live compare。",
                            "aspects": [
                                {
                                    "name": "method",
                                    "summary": "A 与 B 方法不同。",
                                    "per_paper": {
                                        "paper_a": "方法A",
                                        "paper_b": "方法B",
                                    },
                                    "key_differences": ["结构不同"],
                                    "evidence": [
                                        {
                                            "paper_id": "paper_a",
                                            "paper_title": "Paper A",
                                            "section": "Method",
                                            "snippet": "paper A method evidence",
                                        },
                                        {
                                            "paper_id": "paper_b",
                                            "paper_title": "Paper B",
                                            "section": "Method",
                                            "snippet": "paper B method evidence",
                                        },
                                    ],
                                }
                            ],
                            "markdown": "# partial live compare",
                        },
                    }
                ],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    try:
        inject_live_compare_predictions(
            dataset_path=dataset_path, compare_output_path=compare_output_path
        )
    except ValueError as exc:
        error_message = str(exc)
    else:
        raise AssertionError("expected partial live compare payload injection to fail")

    assert (
        "Dataset contains sample_ids missing from live compare payload" in error_message
    )
    assert "cmp-live-partial-002" in error_message


def test_generate_live_compare_predictions_persists_batch_payload(
    tmp_path: Path, monkeypatch
):
    dataset_path = tmp_path / "comparison_eval_seed.jsonl"
    compare_output_path = tmp_path / "comparison_eval_predictions.json"
    _write_jsonl(
        dataset_path,
        [
            {
                "sample_id": "cmp-live-001",
                "question": "比较两篇论文的核心方法。",
                "paper_ids": ["paper_a", "paper_b"],
                "paper_titles": ["Paper A", "Paper B"],
                "expected_summary": "A 偏分类，B 偏检测。",
                "comparison_aspects": ["method"],
                "supporting_sections": {"paper_a": ["Method"], "paper_b": ["Method"]},
                "metadata": {},
            }
        ],
    )

    fake_comparison = PaperComparisonResult.model_validate(
        {
            "overview": "结构化对比已生成。",
            "aspects": [
                {
                    "name": "method",
                    "summary": "A 用 Transformer，B 用 CNN。",
                    "per_paper": {"paper_a": "Transformer", "paper_b": "CNN"},
                    "key_differences": ["网络结构不同"],
                    "evidence": [
                        {
                            "paper_id": "paper_a",
                            "paper_title": "Paper A",
                            "section": "Method",
                            "snippet": "We adopt a Transformer encoder.",
                        }
                    ],
                }
            ],
            "markdown": "# compare output",
            "structured_summaries": {
                "paper_a": {
                    "paper_id": "paper_a",
                    "paper_title": "Paper A",
                    "research_problem": "图像分类",
                    "method": "Transformer",
                    "backbone": "ViT",
                    "dataset": "CIFAR-10",
                    "metrics": "Accuracy",
                    "strengths": "效果稳定",
                    "limitations": "训练成本高",
                    "scenarios": "小样本分类",
                    "evidence": [],
                },
                "paper_b": {
                    "paper_id": "paper_b",
                    "paper_title": "Paper B",
                    "research_problem": "图像分类",
                    "method": "CNN",
                    "backbone": "ResNet",
                    "dataset": "ImageNet",
                    "metrics": "Top-1 Accuracy",
                    "strengths": "易部署",
                    "limitations": "表达能力有限",
                    "scenarios": "大规模分类",
                    "evidence": [],
                },
            },
        }
    )

    def _fake_compare_papers_batch(dataset_path, metadata_dir, llm_client=None):
        assert dataset_path == str(dataset_path_obj)
        assert Path(metadata_dir) == Path("app/storage/metadata")
        return CompareBatchRunResult(
            dataset_path=dataset_path,
            total_samples=1,
            generated_at="2026-05-12T02:00:00Z",
            results=[
                CompareBatchSampleResult(
                    sample_id="cmp-live-001",
                    question="比较两篇论文的核心方法。",
                    paper_ids=["paper_a", "paper_b"],
                    comparison=fake_comparison,
                )
            ],
        )

    dataset_path_obj = dataset_path
    monkeypatch.setattr(
        "app.evaluation.scripts.evaluate_comparison.compare_papers_batch",
        _fake_compare_papers_batch,
    )

    result = generate_live_compare_predictions(
        dataset_path=dataset_path,
        metadata_dir=Path("app/storage/metadata"),
        output_path=compare_output_path,
    )

    saved_payload = json.loads(compare_output_path.read_text(encoding="utf-8"))
    assert result.total_samples == 1
    assert saved_payload["total_samples"] == 1
    assert saved_payload["results"][0]["comparison"]["overview"] == "结构化对比已生成。"
    assert (
        saved_payload["results"][0]["comparison"]["structured_summaries"]["paper_a"][
            "dataset"
        ]
        == "CIFAR-10"
    )


def test_cli_generate_live_compare_reports_missing_metadata_fixture_clearly(
    tmp_path: Path,
):
    dataset_path = tmp_path / "comparison_eval_seed.jsonl"
    compare_output_path = tmp_path / "comparison_eval_predictions.json"
    report_output_path = tmp_path / "comparison_eval_seed_report.json"
    markdown_output_path = tmp_path / "comparison_eval_seed_report.md"
    _write_jsonl(
        dataset_path,
        [
            {
                "sample_id": "cmp-live-cli-001",
                "question": "比较两篇论文的数据集。",
                "paper_ids": ["paper_a", "paper_b"],
                "paper_titles": ["Paper A", "Paper B"],
                "expected_summary": "A 使用 CIFAR-10，B 使用 ImageNet。",
                "comparison_aspects": ["dataset"],
                "supporting_sections": {
                    "paper_a": ["Experiments"],
                    "paper_b": ["Results"],
                },
                "metadata": {},
            }
        ],
    )

    command = [
        sys.executable,
        str(SCRIPT_PATH),
        "--dataset",
        str(dataset_path),
        "--compare-output",
        str(compare_output_path),
        "--output",
        str(report_output_path),
        "--markdown-output",
        str(markdown_output_path),
        "--generate-live-compare",
    ]
    result = subprocess.run(command, capture_output=True, text=True)

    assert result.returncode != 0
    assert "论文解析结果不存在" in result.stderr
    assert "paper_a_parsed.json" in result.stderr


def test_inject_live_compare_predictions_updates_dataset_metadata(tmp_path: Path):
    dataset_path = tmp_path / "comparison_eval_seed.jsonl"
    compare_output_path = tmp_path / "comparison_eval_predictions.json"
    _write_jsonl(
        dataset_path,
        [
            {
                "sample_id": "cmp-live-001",
                "question": "比较两篇论文的核心方法。",
                "paper_ids": ["paper_a", "paper_b"],
                "paper_titles": ["Paper A", "Paper B"],
                "expected_summary": "A 偏分类，B 偏检测。",
                "comparison_aspects": ["method"],
                "supporting_sections": {"paper_a": ["Method"], "paper_b": ["Method"]},
                "metadata": {},
            }
        ],
    )
    compare_output_path.write_text(
        json.dumps(
            {
                "dataset_path": str(dataset_path),
                "total_samples": 1,
                "generated_at": "2026-05-12T03:00:00Z",
                "results": [
                    {
                        "sample_id": "cmp-live-001",
                        "question": "比较两篇论文的核心方法。",
                        "paper_ids": ["paper_a", "paper_b"],
                        "comparison": {
                            "overview": "结构化对比已生成。",
                            "aspects": [
                                {
                                    "name": "method",
                                    "summary": "A 用 Transformer，B 用 CNN。",
                                    "per_paper": {
                                        "paper_a": "Transformer",
                                        "paper_b": "CNN",
                                    },
                                    "key_differences": ["网络结构不同"],
                                    "evidence": [
                                        {
                                            "paper_id": "paper_a",
                                            "paper_title": "Paper A",
                                            "section": "Method",
                                            "snippet": "We adopt a Transformer encoder.",
                                        }
                                    ],
                                }
                            ],
                            "markdown": "# compare output",
                            "structured_summaries": {
                                "paper_a": {
                                    "paper_id": "paper_a",
                                    "paper_title": "Paper A",
                                    "research_problem": "图像分类",
                                    "method": "Transformer",
                                    "backbone": "ViT",
                                    "dataset": "CIFAR-10",
                                    "metrics": "Accuracy",
                                    "strengths": "效果稳定",
                                    "limitations": "训练成本高",
                                    "scenarios": "小样本分类",
                                    "evidence": [],
                                },
                                "paper_b": {
                                    "paper_id": "paper_b",
                                    "paper_title": "Paper B",
                                    "research_problem": "图像分类",
                                    "method": "CNN",
                                    "backbone": "ResNet",
                                    "dataset": "ImageNet",
                                    "metrics": "Top-1 Accuracy",
                                    "strengths": "易部署",
                                    "limitations": "表达能力有限",
                                    "scenarios": "大规模分类",
                                    "evidence": [],
                                },
                            },
                        },
                    }
                ],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    updated_rows = inject_live_compare_predictions(dataset_path, compare_output_path)

    assert len(updated_rows) == 1
    injected = updated_rows[0]
    assert injected["sample_id"] == "cmp-live-001"
    assert (
        injected["metadata"]["predicted_comparison"]["overview"] == "结构化对比已生成。"
    )
    assert (
        injected["metadata"]["predicted_comparison"]["structured_summaries"]["paper_b"][
            "dataset"
        ]
        == "ImageNet"
    )
    persisted_rows = [
        json.loads(line)
        for line in dataset_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert (
        persisted_rows[0]["metadata"]["predicted_comparison"]["overview"]
        == "结构化对比已生成。"
    )


def test_inject_live_compare_predictions_rejects_unknown_sample_ids(tmp_path: Path):
    dataset_path = tmp_path / "comparison_eval_seed.jsonl"
    compare_output_path = tmp_path / "comparison_eval_predictions.json"
    _write_jsonl(
        dataset_path,
        [
            {
                "sample_id": "cmp-live-001",
                "question": "比较两篇论文的核心方法。",
                "paper_ids": ["paper_a", "paper_b"],
                "paper_titles": ["Paper A", "Paper B"],
                "expected_summary": "A 偏分类，B 偏检测。",
                "comparison_aspects": ["method"],
                "supporting_sections": {"paper_a": ["Method"], "paper_b": ["Method"]},
                "metadata": {},
            }
        ],
    )
    compare_output_path.write_text(
        json.dumps(
            {
                "dataset_path": str(dataset_path),
                "total_samples": 1,
                "generated_at": "2026-05-12T03:00:00Z",
                "results": [
                    {
                        "sample_id": "cmp-live-999",
                        "question": "比较两篇论文的核心方法。",
                        "paper_ids": ["paper_a", "paper_b"],
                        "comparison": {
                            "overview": "结构化对比已生成。",
                            "aspects": [],
                            "markdown": "# compare output",
                            "structured_summaries": {},
                        },
                    }
                ],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    try:
        inject_live_compare_predictions(dataset_path, compare_output_path)
        assert False, "Expected ValueError for unknown sample_id"
    except ValueError as exc:
        assert "cmp-live-999" in str(exc)


def test_inject_live_compare_predictions_rejects_missing_prediction_sample_ids(
    tmp_path: Path,
):
    dataset_path = tmp_path / "comparison_eval_seed.jsonl"
    compare_output_path = tmp_path / "comparison_eval_predictions.json"
    _write_jsonl(
        dataset_path,
        [
            {
                "sample_id": "cmp-live-001",
                "question": "比较两篇论文的核心方法。",
                "paper_ids": ["paper_a", "paper_b"],
                "paper_titles": ["Paper A", "Paper B"],
                "expected_summary": "A 偏分类，B 偏检测。",
                "comparison_aspects": ["method"],
                "supporting_sections": {"paper_a": ["Method"], "paper_b": ["Method"]},
                "metadata": {},
            },
            {
                "sample_id": "cmp-live-002",
                "question": "比较两篇论文的数据集。",
                "paper_ids": ["paper_a", "paper_b"],
                "paper_titles": ["Paper A", "Paper B"],
                "expected_summary": "A 与 B 使用不同数据集。",
                "comparison_aspects": ["dataset"],
                "supporting_sections": {
                    "paper_a": ["Experiments"],
                    "paper_b": ["Results"],
                },
                "metadata": {},
            },
        ],
    )
    compare_output_path.write_text(
        json.dumps(
            {
                "dataset_path": str(dataset_path),
                "total_samples": 1,
                "generated_at": "2026-05-12T07:00:00Z",
                "results": [
                    {
                        "sample_id": "cmp-live-001",
                        "question": "比较两篇论文的核心方法。",
                        "paper_ids": ["paper_a", "paper_b"],
                        "comparison": {
                            "overview": "结构化对比已生成。",
                            "aspects": [],
                            "markdown": "# compare output",
                            "structured_summaries": {},
                        },
                    }
                ],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    try:
        inject_live_compare_predictions(dataset_path, compare_output_path)
        assert False, "Expected ValueError for missing dataset sample_id in payload"
    except ValueError as exc:
        assert "cmp-live-002" in str(exc)


def test_compare_batch_returns_live_compare_payloads(tmp_path: Path, monkeypatch):
    dataset_path = tmp_path / "comparison_eval_seed.jsonl"
    _write_jsonl(
        dataset_path,
        [
            {
                "sample_id": "cmp-batch-001",
                "question": "比较两篇论文的方法和数据集。",
                "paper_ids": ["paper_a", "paper_b"],
                "paper_titles": ["Paper A", "Paper B"],
                "expected_summary": "A 与 B 在方法和数据集上不同。",
                "comparison_aspects": ["method", "dataset"],
                "supporting_sections": {
                    "paper_a": ["Method", "Experiments"],
                    "paper_b": ["Method", "Experiments"],
                },
                "metadata": {},
            }
        ],
    )

    fake_comparison = PaperComparisonResult.model_validate(
        {
            "overview": "结构化对比已生成。",
            "aspects": [
                {
                    "name": "method",
                    "summary": "A 用 Transformer，B 用 CNN。",
                    "per_paper": {"paper_a": "Transformer", "paper_b": "CNN"},
                    "key_differences": ["网络结构不同"],
                    "evidence": [
                        {
                            "paper_id": "paper_a",
                            "paper_title": "Paper A",
                            "section": "Method",
                            "snippet": "We adopt a Transformer encoder.",
                        }
                    ],
                }
            ],
            "markdown": "# compare output",
            "structured_summaries": {
                "paper_a": {
                    "paper_id": "paper_a",
                    "paper_title": "Paper A",
                    "research_problem": "图像分类",
                    "method": "Transformer",
                    "backbone": "ViT",
                    "dataset": "CIFAR-10",
                    "metrics": "Accuracy",
                    "strengths": "效果稳定",
                    "limitations": "训练成本高",
                    "scenarios": "小样本分类",
                    "evidence": [],
                },
                "paper_b": {
                    "paper_id": "paper_b",
                    "paper_title": "Paper B",
                    "research_problem": "图像分类",
                    "method": "CNN",
                    "backbone": "ResNet",
                    "dataset": "ImageNet",
                    "metrics": "Top-1 Accuracy",
                    "strengths": "易部署",
                    "limitations": "表达能力有限",
                    "scenarios": "大规模分类",
                    "evidence": [],
                },
            },
        }
    )

    def _fake_compare_papers(paper_ids, metadata_dir, llm_client=None):
        assert paper_ids == ["paper_a", "paper_b"]
        assert metadata_dir == "app/storage/metadata"
        return fake_comparison

    monkeypatch.setattr(
        "app.services.paper_compare.compare_papers", _fake_compare_papers
    )

    batch_result = compare_papers_batch(str(dataset_path), "app/storage/metadata")

    assert isinstance(batch_result, CompareBatchRunResult)
    assert batch_result.total_samples == 1
    assert batch_result.results[0].sample_id == "cmp-batch-001"
    assert batch_result.results[0].comparison.overview == "结构化对比已生成。"
    assert isinstance(
        batch_result.results[0].comparison.structured_summaries["paper_a"],
        PaperStructuredSummary,
    )
    assert (
        batch_result.results[0].comparison.structured_summaries["paper_b"].dataset
        == "ImageNet"
    )


def test_evaluate_comparison_dataset_uses_live_compare_payload_and_flags_misaligned_evidence(
    tmp_path: Path,
):
    dataset_path = tmp_path / "comparison_eval_seed.jsonl"
    _write_jsonl(
        dataset_path,
        [
            {
                "sample_id": "cmp-004",
                "question": "比较两篇论文的方法和数据集。",
                "paper_ids": ["paper_a", "paper_b"],
                "paper_titles": ["Paper A", "Paper B"],
                "expected_summary": "A 与 B 在方法和数据集上存在差异。",
                "comparison_aspects": ["method", "dataset"],
                "supporting_sections": {
                    "paper_a": ["Method", "Experiments"],
                    "paper_b": ["Method", "Experiments"],
                },
                "metadata": {
                    "predicted_comparison": {
                        "overview": "结构化对比已生成。",
                        "aspects": [
                            {
                                "name": "method",
                                "summary": "A 用 Transformer，B 用 CNN。",
                                "per_paper": {
                                    "paper_a": "Transformer",
                                    "paper_b": "CNN",
                                },
                                "key_differences": ["网络结构不同"],
                                "evidence": [
                                    {
                                        "paper_id": "paper_a",
                                        "paper_title": "Paper A",
                                        "section": "Method",
                                        "snippet": "We adopt a Transformer encoder.",
                                    },
                                    {
                                        "paper_id": "paper_b",
                                        "paper_title": "Paper B",
                                        "section": "Method",
                                        "snippet": "The model is built on a CNN backbone.",
                                    },
                                ],
                            },
                            {
                                "name": "dataset",
                                "summary": "A 用 CIFAR-10，B 用 ImageNet。",
                                "per_paper": {
                                    "paper_a": "CIFAR-10",
                                    "paper_b": "ImageNet",
                                },
                                "key_differences": ["训练数据规模不同"],
                                "evidence": [
                                    {
                                        "paper_id": "paper_a",
                                        "paper_title": "Paper A",
                                        "section": "Method",
                                        "snippet": "We adopt a Transformer encoder.",
                                    }
                                ],
                            },
                        ],
                        "markdown": "# live compare payload",
                        "structured_summaries": {
                            "paper_a": {
                                "paper_id": "paper_a",
                                "paper_title": "Paper A",
                                "research_problem": "图像分类",
                                "method": "Transformer",
                                "backbone": "ViT",
                                "dataset": "CIFAR-10",
                                "metrics": "Accuracy",
                                "strengths": "效果稳定",
                                "limitations": "训练成本高",
                                "scenarios": "小样本分类",
                                "evidence": [
                                    {
                                        "paper_id": "paper_a",
                                        "paper_title": "Paper A",
                                        "section": "Experiments",
                                        "snippet": "We evaluate on CIFAR-10.",
                                    }
                                ],
                            },
                            "paper_b": {
                                "paper_id": "paper_b",
                                "paper_title": "Paper B",
                                "research_problem": "图像分类",
                                "method": "CNN",
                                "backbone": "ResNet",
                                "dataset": "ImageNet",
                                "metrics": "Top-1 Accuracy",
                                "strengths": "易部署",
                                "limitations": "表达能力有限",
                                "scenarios": "大规模分类",
                                "evidence": [
                                    {
                                        "paper_id": "paper_b",
                                        "paper_title": "Paper B",
                                        "section": "Experiments",
                                        "snippet": "Experiments are conducted on ImageNet.",
                                    }
                                ],
                            },
                        },
                    }
                },
            }
        ],
    )

    report = evaluate_comparison_dataset(dataset_path)
    result = report["results"][0]

    assert result["comparison_source"] == "predicted_comparison"
    assert result["uses_structured_summaries"] is True
    assert result["evidence_quality_issues"] == ["dataset"]
    assert result["evidence_quality"] == 0.5
    assert result["evidence_completeness"] == 1.0
    assert report["summary"]["mean_evidence_quality"] == 0.5
