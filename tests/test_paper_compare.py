import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.schemas import (
    CompareAspect,
    CompareResponse,
    PaperComparisonResult,
    PaperEvidence,
    PaperStructuredSummary,
)
from app.services import paper_compare


class StubLLMClient:
    def __init__(self, response: str):
        self.response = response
        self.prompts: list[str] = []

    def generate_text(self, prompt: str) -> str:
        self.prompts.append(prompt)
        return self.response


@pytest.fixture
def sample_parsed_papers(tmp_path: Path) -> str:
    metadata_dir = tmp_path / "metadata"
    metadata_dir.mkdir()

    paper_a = {
        "paper_id": "paper_a",
        "title": "Paper A",
        "abstract": "Paper A abstract",
        "sections": [
            {
                "heading": "Method",
                "content": "Transformer backbone for classification.",
            },
            {
                "heading": "Experiments",
                "content": "Evaluated on CIFAR-10 with accuracy.",
            },
        ],
        "full_text": "full text a",
        "pdf_path": "paper_a.pdf",
    }
    paper_b = {
        "paper_id": "paper_b",
        "title": "Paper B",
        "abstract": "Paper B abstract",
        "sections": [
            {"heading": "Method", "content": "CNN backbone for detection."},
            {"heading": "Results", "content": "Evaluated on COCO with mAP."},
        ],
        "full_text": "full text b",
        "pdf_path": "paper_b.pdf",
    }

    (metadata_dir / "paper_a_parsed.json").write_text(
        json.dumps(paper_a, ensure_ascii=False), encoding="utf-8"
    )
    (metadata_dir / "paper_b_parsed.json").write_text(
        json.dumps(paper_b, ensure_ascii=False), encoding="utf-8"
    )
    return str(metadata_dir)


def test_compare_papers_returns_structured_and_markdown_outputs(
    sample_parsed_papers: str,
):
    llm_output = {
        "overview": "两篇论文都关注视觉任务，但方法路线不同。",
        "aspects": [
            {
                "name": "method",
                "summary": "Paper A 使用 Transformer，Paper B 使用 CNN。",
                "key_differences": ["A 更偏表示学习", "B 更偏检测任务"],
                "per_paper": {
                    "paper_a": "Transformer backbone",
                    "paper_b": "CNN backbone",
                },
                "evidence": [
                    {
                        "paper_id": "paper_a",
                        "paper_title": "Paper A",
                        "section": "Method",
                        "snippet": "Transformer backbone for classification.",
                    },
                    {
                        "paper_id": "paper_b",
                        "paper_title": "Paper B",
                        "section": "Method",
                        "snippet": "CNN backbone for detection.",
                    },
                ],
            }
        ],
    }
    llm_client = StubLLMClient(json.dumps(llm_output, ensure_ascii=False))

    result = paper_compare.compare_papers(
        ["paper_a", "paper_b"],
        sample_parsed_papers,
        llm_client=llm_client,
    )

    assert isinstance(result, PaperComparisonResult)
    assert result.overview == llm_output["overview"]
    assert result.aspects[0].name == "method"
    assert result.aspects[0].per_paper["paper_a"] == "Transformer backbone"
    assert "## 总览" in result.markdown
    assert "| 维度 | Paper A | Paper B |" in result.markdown
    assert "## 证据摘录" in result.markdown
    assert "Transformer backbone for classification." in result.markdown
    assert llm_client.prompts


def test_compare_papers_rejects_invalid_json_response(sample_parsed_papers: str):
    llm_client = StubLLMClient("not-json")

    with pytest.raises(RuntimeError, match="单篇结构化抽取结果解析失败"):
        paper_compare.compare_papers(
            ["paper_a", "paper_b"],
            sample_parsed_papers,
            llm_client=llm_client,
        )


def test_compare_papers_rejects_invalid_compare_stage_json(sample_parsed_papers: str):
    extraction_output = {
        "paper_a": {
            "research_problem": "图像分类",
            "method": "Transformer",
            "backbone": "ViT",
            "dataset": "CIFAR-10",
            "metrics": "Accuracy",
            "strengths": "全局建模",
            "limitations": "算力开销高",
            "scenarios": "图像分类",
            "evidence": [
                {
                    "section": "Method",
                    "snippet": "Transformer backbone for classification.",
                }
            ],
        },
        "paper_b": {
            "research_problem": "目标检测",
            "method": "CNN",
            "backbone": "ResNet",
            "dataset": "COCO",
            "metrics": "mAP",
            "strengths": "局部检测",
            "limitations": "长程依赖较弱",
            "scenarios": "目标检测",
            "evidence": [
                {"section": "Method", "snippet": "CNN backbone for detection."}
            ],
        },
    }
    llm_client = StubLLMClient("")
    calls = {"count": 0}

    def two_stage_generate(prompt: str) -> str:
        calls["count"] += 1
        if calls["count"] == 1:
            return json.dumps(extraction_output, ensure_ascii=False)
        return "not-json"

    llm_client.generate_text = two_stage_generate

    with pytest.raises(RuntimeError, match="结构化对比结果解析失败"):
        paper_compare.compare_papers(
            ["paper_a", "paper_b"],
            sample_parsed_papers,
            llm_client=llm_client,
        )


def test_compare_papers_rejects_non_dict_compare_stage_payload(
    sample_parsed_papers: str,
):
    extraction_output = {
        "paper_a": {
            "research_problem": "图像分类",
            "method": "Transformer",
            "backbone": "ViT",
            "dataset": "CIFAR-10",
            "metrics": "Accuracy",
            "strengths": "全局建模",
            "limitations": "算力开销高",
            "scenarios": "图像分类",
            "evidence": [
                {
                    "section": "Method",
                    "snippet": "Transformer backbone for classification.",
                }
            ],
        },
        "paper_b": {
            "research_problem": "目标检测",
            "method": "CNN",
            "backbone": "ResNet",
            "dataset": "COCO",
            "metrics": "mAP",
            "strengths": "局部检测",
            "limitations": "长程依赖较弱",
            "scenarios": "目标检测",
            "evidence": [
                {"section": "Method", "snippet": "CNN backbone for detection."}
            ],
        },
    }
    llm_client = StubLLMClient("")
    calls = {"count": 0}

    def two_stage_generate(prompt: str) -> str:
        calls["count"] += 1
        if calls["count"] == 1:
            return json.dumps(extraction_output, ensure_ascii=False)
        return json.dumps([], ensure_ascii=False)

    llm_client.generate_text = two_stage_generate

    with pytest.raises(RuntimeError, match="结构化对比结果解析失败"):
        paper_compare.compare_papers(
            ["paper_a", "paper_b"],
            sample_parsed_papers,
            llm_client=llm_client,
        )


def test_compare_papers_normalizes_blank_compare_overview_and_summary(
    sample_parsed_papers: str,
):
    extraction_output = {
        "paper_a": {
            "research_problem": "图像分类",
            "method": "Transformer",
            "backbone": "ViT",
            "dataset": "CIFAR-10",
            "metrics": "Accuracy",
            "strengths": "全局建模",
            "limitations": "算力开销高",
            "scenarios": "图像分类",
            "evidence": [
                {
                    "section": "Method",
                    "snippet": "Transformer backbone for classification.",
                }
            ],
        },
        "paper_b": {
            "research_problem": "目标检测",
            "method": "CNN",
            "backbone": "ResNet",
            "dataset": "COCO",
            "metrics": "mAP",
            "strengths": "局部检测",
            "limitations": "长程依赖较弱",
            "scenarios": "目标检测",
            "evidence": [
                {"section": "Method", "snippet": "CNN backbone for detection."}
            ],
        },
    }
    compare_output = {
        "overview": "   ",
        "aspects": [
            {
                "name": "method",
                "summary": None,
                "key_differences": ["A 更偏表示学习"],
                "per_paper": {
                    "paper_a": "Transformer backbone",
                    "paper_b": "CNN backbone",
                },
                "evidence": [],
            }
        ],
    }
    llm_client = StubLLMClient("")
    calls = {"count": 0}

    def two_stage_generate(prompt: str) -> str:
        calls["count"] += 1
        if calls["count"] == 1:
            return json.dumps(extraction_output, ensure_ascii=False)
        return json.dumps(compare_output, ensure_ascii=False)

    llm_client.generate_text = two_stage_generate

    result = paper_compare.compare_papers(
        ["paper_a", "paper_b"],
        sample_parsed_papers,
        llm_client=llm_client,
    )

    assert result.overview == "未明确说明"
    assert result.aspects[0].summary == "未明确说明"
    assert "## 总览\n未明确说明" in result.markdown


def test_compare_papers_replaces_non_list_key_differences_with_empty_list(
    sample_parsed_papers: str,
):
    extraction_output = {
        "paper_a": {
            "research_problem": "图像分类",
            "method": "Transformer",
            "backbone": "ViT",
            "dataset": "CIFAR-10",
            "metrics": "Accuracy",
            "strengths": "全局建模",
            "limitations": "算力开销高",
            "scenarios": "图像分类",
            "evidence": [
                {
                    "section": "Method",
                    "snippet": "Transformer backbone for classification.",
                }
            ],
        },
        "paper_b": {
            "research_problem": "目标检测",
            "method": "CNN",
            "backbone": "ResNet",
            "dataset": "COCO",
            "metrics": "mAP",
            "strengths": "局部检测",
            "limitations": "长程依赖较弱",
            "scenarios": "目标检测",
            "evidence": [
                {"section": "Method", "snippet": "CNN backbone for detection."}
            ],
        },
    }
    compare_output = {
        "overview": "两篇论文都关注视觉任务，但方法路线不同。",
        "aspects": [
            {
                "name": "method",
                "summary": "Paper A 使用 Transformer，Paper B 使用 CNN。",
                "key_differences": "not-a-list",
                "per_paper": {
                    "paper_a": "Transformer backbone",
                    "paper_b": "CNN backbone",
                },
                "evidence": [],
            }
        ],
    }
    llm_client = StubLLMClient("")
    calls = {"count": 0}

    def two_stage_generate(prompt: str) -> str:
        calls["count"] += 1
        if calls["count"] == 1:
            return json.dumps(extraction_output, ensure_ascii=False)
        return json.dumps(compare_output, ensure_ascii=False)

    llm_client.generate_text = two_stage_generate

    result = paper_compare.compare_papers(
        ["paper_a", "paper_b"],
        sample_parsed_papers,
        llm_client=llm_client,
    )

    assert result.aspects[0].key_differences == []


def test_compare_papers_escapes_markdown_table_cells(sample_parsed_papers: str):
    extraction_output = {
        "paper_a": {
            "research_problem": "图像分类",
            "method": "Transformer",
            "backbone": "ViT",
            "dataset": "CIFAR-10",
            "metrics": "Accuracy",
            "strengths": "全局建模",
            "limitations": "算力开销高",
            "scenarios": "图像分类",
            "evidence": [
                {
                    "section": "Method",
                    "snippet": "Transformer backbone for classification.",
                }
            ],
        },
        "paper_b": {
            "research_problem": "目标检测",
            "method": "CNN",
            "backbone": "ResNet",
            "dataset": "COCO",
            "metrics": "mAP",
            "strengths": "局部检测",
            "limitations": "长程依赖较弱",
            "scenarios": "目标检测",
            "evidence": [
                {"section": "Method", "snippet": "CNN backbone for detection."}
            ],
        },
    }
    compare_output = {
        "overview": "包含表格特殊字符。",
        "aspects": [
            {
                "name": "method",
                "summary": "Transformer | CNN\n第二行",
                "key_differences": ["A 更偏表示学习"],
                "per_paper": {
                    "paper_a": "Transformer | backbone",
                    "paper_b": "CNN\nbackbone",
                },
                "evidence": [],
            }
        ],
    }
    llm_client = StubLLMClient("")
    calls = {"count": 0}

    def two_stage_generate(prompt: str) -> str:
        calls["count"] += 1
        if calls["count"] == 1:
            return json.dumps(extraction_output, ensure_ascii=False)
        return json.dumps(compare_output, ensure_ascii=False)

    llm_client.generate_text = two_stage_generate

    parsed_dir = Path(sample_parsed_papers)
    paper_a_path = parsed_dir / "paper_a_parsed.json"
    paper_a_payload = json.loads(paper_a_path.read_text(encoding="utf-8"))
    paper_a_payload["title"] = "Paper | A"
    paper_a_path.write_text(
        json.dumps(paper_a_payload, ensure_ascii=False), encoding="utf-8"
    )

    result = paper_compare.compare_papers(
        ["paper_a", "paper_b"],
        sample_parsed_papers,
        llm_client=llm_client,
    )

    assert "| 维度 | Paper \\| A | Paper B | 总结 |" in result.markdown
    assert "Transformer \\| backbone" in result.markdown
    assert "CNN<br>backbone" in result.markdown
    assert "Transformer \\| CNN<br>第二行" in result.markdown


def test_compare_papers_ignores_non_dict_aspect_entries(sample_parsed_papers: str):
    extraction_output = {
        "paper_a": {
            "research_problem": "图像分类",
            "method": "Transformer",
            "backbone": "ViT",
            "dataset": "CIFAR-10",
            "metrics": "Accuracy",
            "strengths": "全局建模",
            "limitations": "算力开销高",
            "scenarios": "图像分类",
            "evidence": [
                {
                    "section": "Method",
                    "snippet": "Transformer backbone for classification.",
                }
            ],
        },
        "paper_b": {
            "research_problem": "目标检测",
            "method": "CNN",
            "backbone": "ResNet",
            "dataset": "COCO",
            "metrics": "mAP",
            "strengths": "局部检测",
            "limitations": "长程依赖较弱",
            "scenarios": "目标检测",
            "evidence": [
                {"section": "Method", "snippet": "CNN backbone for detection."}
            ],
        },
    }
    compare_output = {
        "overview": "两篇论文都关注视觉任务，但方法路线不同。",
        "aspects": [
            "bad-item",
            {
                "name": "method",
                "summary": "Paper A 使用 Transformer，Paper B 使用 CNN。",
                "key_differences": ["A 更偏表示学习"],
                "per_paper": {
                    "paper_a": "Transformer backbone",
                    "paper_b": "CNN backbone",
                },
                "evidence": [],
            },
        ],
    }
    llm_client = StubLLMClient("")
    calls = {"count": 0}

    def two_stage_generate(prompt: str) -> str:
        calls["count"] += 1
        if calls["count"] == 1:
            return json.dumps(extraction_output, ensure_ascii=False)
        return json.dumps(compare_output, ensure_ascii=False)

    llm_client.generate_text = two_stage_generate

    result = paper_compare.compare_papers(
        ["paper_a", "paper_b"],
        sample_parsed_papers,
        llm_client=llm_client,
    )

    assert len(result.aspects) == 1
    assert result.aspects[0].name == "method"
    assert "Paper A 使用 Transformer" in result.markdown


def test_compare_papers_propagates_structured_summaries_in_response(
    sample_parsed_papers: str,
):
    extraction_output = {
        "paper_a": {
            "research_problem": "图像分类中的表示学习。",
            "method": "Transformer backbone with supervised training.",
            "backbone": "Vision Transformer",
            "dataset": "CIFAR-10",
            "metrics": "Accuracy",
            "strengths": "全局建模能力强。",
            "limitations": "对算力要求较高。",
            "scenarios": "中等规模图像分类任务。",
            "evidence": [
                {
                    "section": "Method",
                    "snippet": "Transformer backbone for classification.",
                }
            ],
        },
        "paper_b": {
            "research_problem": "目标检测中的局部特征建模。",
            "method": "CNN backbone for detection.",
            "backbone": "ResNet",
            "dataset": "COCO",
            "metrics": "mAP",
            "strengths": "局部感受野强，检测成熟。",
            "limitations": "长程依赖建模较弱。",
            "scenarios": "通用检测任务。",
            "evidence": [
                {"section": "Results", "snippet": "Evaluated on COCO with mAP."}
            ],
        },
    }
    compare_output = {
        "overview": "两篇论文都关注视觉任务，但方法路线不同。",
        "aspects": [
            {
                "name": "method",
                "summary": "Paper A 使用 Transformer，Paper B 使用 CNN。",
                "key_differences": ["A 更偏表示学习", "B 更偏检测任务"],
                "per_paper": {
                    "paper_a": "Transformer backbone",
                    "paper_b": "CNN backbone",
                },
                "evidence": [
                    {
                        "paper_id": "paper_a",
                        "paper_title": "Paper A",
                        "section": "Method",
                        "snippet": "Transformer backbone for classification.",
                    },
                    {
                        "paper_id": "paper_b",
                        "paper_title": "Paper B",
                        "section": "Method",
                        "snippet": "CNN backbone for detection.",
                    },
                ],
            }
        ],
    }

    llm_client = StubLLMClient("")
    calls = {"count": 0}

    def two_stage_generate(prompt: str) -> str:
        calls["count"] += 1
        if calls["count"] == 1:
            return json.dumps(extraction_output, ensure_ascii=False)
        return json.dumps(compare_output, ensure_ascii=False)

    llm_client.generate_text = two_stage_generate

    result = paper_compare.compare_papers(
        ["paper_a", "paper_b"],
        sample_parsed_papers,
        llm_client=llm_client,
    )

    assert result.structured_summaries is not None
    assert set(result.structured_summaries) == {"paper_a", "paper_b"}
    assert result.structured_summaries["paper_a"].dataset == "CIFAR-10"
    assert result.structured_summaries["paper_b"].metrics == "mAP"


def test_extract_paper_summaries_returns_per_paper_structured_fields(
    sample_parsed_papers: str,
):
    llm_outputs = {
        "paper_a": {
            "research_problem": "图像分类中的表示学习。",
            "method": "Transformer backbone with supervised training.",
            "backbone": "Vision Transformer",
            "dataset": "CIFAR-10",
            "metrics": "Accuracy",
            "strengths": "全局建模能力强。",
            "limitations": "对算力要求较高。",
            "scenarios": "中等规模图像分类任务。",
            "evidence": [
                {
                    "section": "Method",
                    "snippet": "Transformer backbone for classification.",
                }
            ],
        },
        "paper_b": {
            "research_problem": "目标检测中的局部特征建模。",
            "method": "CNN backbone for detection.",
            "backbone": "ResNet",
            "dataset": "COCO",
            "metrics": "mAP",
            "strengths": "局部感受野强，检测成熟。",
            "limitations": "长程依赖建模较弱。",
            "scenarios": "通用检测任务。",
            "evidence": [
                {
                    "section": "Results",
                    "snippet": "Evaluated on COCO with mAP.",
                }
            ],
        },
    }
    llm_client = StubLLMClient(json.dumps(llm_outputs, ensure_ascii=False))

    summaries = paper_compare.extract_paper_summaries(
        ["paper_a", "paper_b"],
        sample_parsed_papers,
        llm_client=llm_client,
    )

    assert set(summaries) == {"paper_a", "paper_b"}
    assert isinstance(summaries["paper_a"], PaperStructuredSummary)
    assert summaries["paper_a"].dataset == "CIFAR-10"
    assert summaries["paper_b"].metrics == "mAP"
    assert summaries["paper_a"].evidence[0].paper_id == "paper_a"
    assert summaries["paper_b"].evidence[0].paper_title == "Paper B"
    assert llm_client.prompts


def test_extract_paper_summaries_defaults_missing_fields_to_未明确说明(
    sample_parsed_papers: str,
):
    llm_outputs = {
        "paper_a": {
            "method": "Transformer backbone with supervised training.",
            "evidence": [
                {
                    "section": "Method",
                    "snippet": "Transformer backbone for classification.",
                }
            ],
        },
        "paper_b": {},
    }
    llm_client = StubLLMClient(json.dumps(llm_outputs, ensure_ascii=False))

    summaries = paper_compare.extract_paper_summaries(
        ["paper_a", "paper_b"],
        sample_parsed_papers,
        llm_client=llm_client,
    )

    assert summaries["paper_a"].research_problem == "未明确说明"
    assert (
        summaries["paper_a"].method == "Transformer backbone with supervised training."
    )
    assert summaries["paper_b"].dataset == "未明确说明"
    assert summaries["paper_b"].strengths == "未明确说明"
    assert summaries["paper_b"].evidence == []


def test_extract_paper_summaries_tolerates_non_dict_top_level_and_non_dict_per_paper_payload(
    sample_parsed_papers: str,
):
    top_level_non_dict_client = StubLLMClient(json.dumps([], ensure_ascii=False))

    with pytest.raises(RuntimeError, match="单篇结构化抽取结果解析失败"):
        paper_compare.extract_paper_summaries(
            ["paper_a", "paper_b"],
            sample_parsed_papers,
            llm_client=top_level_non_dict_client,
        )

    llm_outputs = {
        "paper_a": ["invalid-payload"],
        "paper_b": {
            "method": "CNN backbone for detection.",
        },
    }
    llm_client = StubLLMClient(json.dumps(llm_outputs, ensure_ascii=False))

    summaries = paper_compare.extract_paper_summaries(
        ["paper_a", "paper_b"],
        sample_parsed_papers,
        llm_client=llm_client,
    )

    assert summaries["paper_a"].research_problem == "未明确说明"
    assert summaries["paper_a"].method == "未明确说明"
    assert summaries["paper_a"].evidence == []
    assert summaries["paper_b"].method == "CNN backbone for detection."
    assert summaries["paper_b"].dataset == "未明确说明"


def test_compare_papers_uses_structured_extraction_before_comparison(
    sample_parsed_papers: str,
):
    llm_output = {
        "overview": "两篇论文都关注视觉任务，但方法路线不同。",
        "aspects": [
            {
                "name": "method",
                "summary": "Paper A 使用 Transformer，Paper B 使用 CNN。",
                "key_differences": ["A 更偏表示学习", "B 更偏检测任务"],
                "per_paper": {
                    "paper_a": "Transformer backbone",
                    "paper_b": "CNN backbone",
                },
                "evidence": [
                    {
                        "paper_id": "paper_a",
                        "paper_title": "Paper A",
                        "section": "Method",
                        "snippet": "Transformer backbone for classification.",
                    },
                    {
                        "paper_id": "paper_b",
                        "paper_title": "Paper B",
                        "section": "Method",
                        "snippet": "CNN backbone for detection.",
                    },
                ],
            }
        ],
    }

    extracted = {
        "paper_a": PaperStructuredSummary(
            paper_id="paper_a",
            paper_title="Paper A",
            research_problem="分类",
            method="Transformer backbone",
            backbone="ViT",
            dataset="CIFAR-10",
            metrics="Accuracy",
            strengths="全局建模",
            limitations="算力开销高",
            scenarios="图像分类",
            evidence=[
                PaperEvidence(
                    paper_id="paper_a",
                    paper_title="Paper A",
                    section="Method",
                    snippet="Transformer backbone for classification.",
                )
            ],
        ),
        "paper_b": PaperStructuredSummary(
            paper_id="paper_b",
            paper_title="Paper B",
            research_problem="检测",
            method="CNN backbone",
            backbone="ResNet",
            dataset="COCO",
            metrics="mAP",
            strengths="局部检测",
            limitations="长程依赖较弱",
            scenarios="目标检测",
            evidence=[
                PaperEvidence(
                    paper_id="paper_b",
                    paper_title="Paper B",
                    section="Method",
                    snippet="CNN backbone for detection.",
                )
            ],
        ),
    }

    llm_client = StubLLMClient(json.dumps(llm_output, ensure_ascii=False))
    captured: dict[str, str] = {}
    original_prompt_builder = paper_compare.build_compare_prompt

    def capture_prompt(papers_text: str) -> str:
        captured["papers_text"] = papers_text
        return original_prompt_builder(papers_text)

    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setattr(
        paper_compare, "extract_paper_summaries", lambda *args, **kwargs: extracted
    )
    monkeypatch.setattr(paper_compare, "build_compare_prompt", capture_prompt)
    try:
        result = paper_compare.compare_papers(
            ["paper_a", "paper_b"],
            sample_parsed_papers,
            llm_client=llm_client,
        )
    finally:
        monkeypatch.undo()

    assert result.aspects[0].name == "method"
    assert "## Structured Paper Summaries" in captured["papers_text"]
    assert '"paper_id": "paper_a"' in captured["papers_text"]
    assert '"dataset": "COCO"' in captured["papers_text"]


def test_compare_papers_infers_missing_aspect_evidence_from_structured_summaries(
    sample_parsed_papers: str,
):
    llm_output = {
        "overview": "两篇论文都关注视觉任务，但方法路线不同。",
        "aspects": [
            {
                "name": "method",
                "summary": "Paper A 使用 Transformer，Paper B 使用 CNN。",
                "key_differences": ["A 更偏表示学习", "B 更偏检测任务"],
                "per_paper": {
                    "paper_a": "Transformer backbone",
                    "paper_b": "CNN backbone",
                },
                "evidence": [],
            }
        ],
    }

    extracted = {
        "paper_a": PaperStructuredSummary(
            paper_id="paper_a",
            paper_title="Paper A",
            research_problem="分类",
            method="Transformer backbone",
            backbone="ViT",
            dataset="CIFAR-10",
            metrics="Accuracy",
            strengths="全局建模",
            limitations="算力开销高",
            scenarios="图像分类",
            evidence=[
                PaperEvidence(
                    paper_id="paper_a",
                    paper_title="Paper A",
                    section="Method",
                    snippet="Transformer backbone for classification.",
                )
            ],
        ),
        "paper_b": PaperStructuredSummary(
            paper_id="paper_b",
            paper_title="Paper B",
            research_problem="检测",
            method="CNN backbone",
            backbone="ResNet",
            dataset="COCO",
            metrics="mAP",
            strengths="局部检测",
            limitations="长程依赖较弱",
            scenarios="目标检测",
            evidence=[
                PaperEvidence(
                    paper_id="paper_b",
                    paper_title="Paper B",
                    section="Method",
                    snippet="CNN backbone for detection.",
                )
            ],
        ),
    }

    llm_client = StubLLMClient(json.dumps(llm_output, ensure_ascii=False))
    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setattr(
        paper_compare, "extract_paper_summaries", lambda *args, **kwargs: extracted
    )
    try:
        result = paper_compare.compare_papers(
            ["paper_a", "paper_b"],
            sample_parsed_papers,
            llm_client=llm_client,
        )
    finally:
        monkeypatch.undo()

    method_aspect = result.aspects[0]
    assert method_aspect.name == "method"
    assert [e.paper_id for e in method_aspect.evidence] == ["paper_a", "paper_b"]
    assert method_aspect.evidence[0].section == "Method"
    assert "Transformer backbone for classification." in result.markdown


def test_compare_papers_normalizes_blank_or_invalid_aspect_name_to_unknown(
    sample_parsed_papers: str,
):
    extraction_output = {
        "paper_a": {
            "research_problem": "图像分类",
            "method": "Transformer",
            "backbone": "ViT",
            "dataset": "CIFAR-10",
            "metrics": "Accuracy",
            "strengths": "全局建模",
            "limitations": "算力开销高",
            "scenarios": "图像分类",
            "evidence": [
                {
                    "section": "Method",
                    "snippet": "Transformer backbone for classification.",
                }
            ],
        },
        "paper_b": {
            "research_problem": "目标检测",
            "method": "CNN",
            "backbone": "ResNet",
            "dataset": "COCO",
            "metrics": "mAP",
            "strengths": "局部检测",
            "limitations": "长程依赖较弱",
            "scenarios": "目标检测",
            "evidence": [
                {"section": "Method", "snippet": "CNN backbone for detection."}
            ],
        },
    }
    compare_output = {
        "overview": "两篇论文都关注视觉任务，但方法路线不同。",
        "aspects": [
            {
                "name": "   ",
                "summary": "方法路线不同。",
                "key_differences": [],
                "per_paper": {
                    "paper_a": "Transformer",
                    "paper_b": "CNN",
                },
                "evidence": [],
            }
        ],
    }

    llm_client = StubLLMClient("")
    calls = {"count": 0}

    def two_stage_generate(prompt: str) -> str:
        calls["count"] += 1
        if calls["count"] == 1:
            return json.dumps(extraction_output, ensure_ascii=False)
        return json.dumps(compare_output, ensure_ascii=False)

    llm_client.generate_text = two_stage_generate

    result = paper_compare.compare_papers(
        ["paper_a", "paper_b"],
        sample_parsed_papers,
        llm_client=llm_client,
    )

    assert result.aspects[0].name == "unknown"
    assert "| unknown | Transformer | CNN | 方法路线不同。 |" in result.markdown


def test_compare_papers_normalizes_blank_or_invalid_per_paper_values(
    sample_parsed_papers: str,
):
    extraction_output = {
        "paper_a": {
            "research_problem": "图像分类",
            "method": "Transformer",
            "backbone": "ViT",
            "dataset": "CIFAR-10",
            "metrics": "Accuracy",
            "strengths": "全局建模",
            "limitations": "算力开销高",
            "scenarios": "图像分类",
            "evidence": [
                {
                    "section": "Method",
                    "snippet": "Transformer backbone for classification.",
                }
            ],
        },
        "paper_b": {
            "research_problem": "目标检测",
            "method": "CNN",
            "backbone": "ResNet",
            "dataset": "COCO",
            "metrics": "mAP",
            "strengths": "局部检测",
            "limitations": "长程依赖较弱",
            "scenarios": "目标检测",
            "evidence": [
                {"section": "Results", "snippet": "Evaluated on COCO with mAP."}
            ],
        },
    }
    compare_output = {
        "overview": "两篇论文都关注视觉任务，但方法路线不同。",
        "aspects": [
            {
                "name": "method",
                "summary": "方法路线不同。",
                "key_differences": ["A 更偏表示学习", "B 更偏检测任务"],
                "per_paper": {
                    "paper_a": "   ",
                    "paper_b": None,
                },
                "evidence": [],
            }
        ],
    }

    llm_client = StubLLMClient("")
    calls = {"count": 0}

    def two_stage_generate(prompt: str) -> str:
        calls["count"] += 1
        if calls["count"] == 1:
            return json.dumps(extraction_output, ensure_ascii=False)
        return json.dumps(compare_output, ensure_ascii=False)

    llm_client.generate_text = two_stage_generate

    result = paper_compare.compare_papers(
        ["paper_a", "paper_b"],
        sample_parsed_papers,
        llm_client=llm_client,
    )

    assert result.aspects[0].per_paper["paper_a"] == "未明确说明"
    assert result.aspects[0].per_paper["paper_b"] == "未明确说明"
    assert "| 核心方法 | 未明确说明 | 未明确说明 | 方法路线不同。 |" in result.markdown


def test_compare_papers_tolerates_non_list_or_invalid_compare_stage_evidence(
    sample_parsed_papers: str,
):
    extraction_output = {
        "paper_a": {
            "research_problem": "图像分类",
            "method": "Transformer",
            "backbone": "ViT",
            "dataset": "CIFAR-10",
            "metrics": "Accuracy",
            "strengths": "全局建模",
            "limitations": "算力开销高",
            "scenarios": "图像分类",
            "evidence": [
                {
                    "section": "Method",
                    "snippet": "Transformer backbone for classification.",
                }
            ],
        },
        "paper_b": {
            "research_problem": "目标检测",
            "method": "CNN",
            "backbone": "ResNet",
            "dataset": "COCO",
            "metrics": "mAP",
            "strengths": "局部检测",
            "limitations": "长程依赖较弱",
            "scenarios": "目标检测",
            "evidence": [
                {"section": "Results", "snippet": "Evaluated on COCO with mAP."}
            ],
        },
    }
    compare_output = {
        "overview": "两篇论文都关注视觉任务，但方法路线不同。",
        "aspects": [
            {
                "name": "method",
                "summary": "方法路线不同。",
                "key_differences": ["A 更偏表示学习", "B 更偏检测任务"],
                "per_paper": {
                    "paper_a": "Transformer",
                    "paper_b": "CNN",
                },
                "evidence": [
                    "bad-evidence",
                    {"paper_id": "paper_a"},
                    {
                        "paper_id": "paper_a",
                        "paper_title": "Paper A",
                        "section": "Method",
                        "snippet": "Transformer backbone for classification.",
                    },
                ],
            }
        ],
    }

    llm_client = StubLLMClient("")
    calls = {"count": 0}

    def two_stage_generate(prompt: str) -> str:
        calls["count"] += 1
        if calls["count"] == 1:
            return json.dumps(extraction_output, ensure_ascii=False)
        return json.dumps(compare_output, ensure_ascii=False)

    llm_client.generate_text = two_stage_generate

    result = paper_compare.compare_papers(
        ["paper_a", "paper_b"],
        sample_parsed_papers,
        llm_client=llm_client,
    )

    method_aspect = result.aspects[0]
    assert [e.paper_id for e in method_aspect.evidence] == ["paper_a"]
    assert (
        method_aspect.evidence[0].snippet == "Transformer backbone for classification."
    )
    assert "Transformer backbone for classification." in result.markdown


def test_compare_response_model_accepts_structured_payload():
    response = CompareResponse(
        paper_ids=["paper_a", "paper_b"],
        status="compared",
        output_path="notes/compare_x.md",
        content="# markdown",
        comparison=PaperComparisonResult(
            overview="overview",
            aspects=[
                CompareAspect(
                    name="method",
                    summary="summary",
                    key_differences=["diff"],
                    per_paper={"paper_a": "A", "paper_b": "B"},
                    evidence=[
                        PaperEvidence(
                            paper_id="paper_a",
                            paper_title="Paper A",
                            section="Method",
                            snippet="snippet",
                        )
                    ],
                )
            ],
            markdown="# markdown",
        ),
    )

    assert response.comparison is not None
    assert response.comparison.aspects[0].name == "method"


def test_compare_endpoint_returns_structured_result(monkeypatch):
    structured = PaperComparisonResult(
        overview="overview",
        aspects=[
            CompareAspect(
                name="dataset",
                summary="summary",
                key_differences=["diff"],
                per_paper={"paper_a": "CIFAR-10", "paper_b": "COCO"},
                evidence=[
                    PaperEvidence(
                        paper_id="paper_a",
                        paper_title="Paper A",
                        section="Experiments",
                        snippet="Evaluated on CIFAR-10.",
                    )
                ],
            )
        ],
        markdown="# compare markdown",
    )

    monkeypatch.setattr("app.main.compare_papers", lambda *args, **kwargs: structured)
    monkeypatch.setattr(
        "app.main.save_compare_result", lambda markdown, note_dir: "/tmp/compare.md"
    )

    client = TestClient(app)
    response = client.post(
        "/papers/compare", json={"paper_ids": ["paper_a", "paper_b"]}
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["content"] == "# compare markdown"
    assert payload["comparison"]["overview"] == "overview"
    assert payload["comparison"]["aspects"][0]["name"] == "dataset"
