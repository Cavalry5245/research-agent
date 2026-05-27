import json
import os
import sys
import tempfile
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.prompts.paper_note_prompt import build_note_prompt
from app.services.markdown_exporter import save_markdown
from app.services.note_generator import _build_paper_content, generate_note
from app.services.pdf_parser import load_parsed_result

MOCK_MARKDOWN = """# 论文阅读笔记：Test Paper

## 1. 基本信息
- 论文标题：Test Paper
- 作者：原文未明确说明
- 发表年份：原文未明确说明
- 会议/期刊：原文未明确说明
- 研究任务：目标检测
- 方法类别：深度学习
- 应用场景：红外小目标检测
- 关键词：VLM, 注意力机制

## 2. 研究背景
测试背景内容。

## 3. 核心问题
测试核心问题。

## 4. 方法概述
测试方法。

## 5. 模型结构 / 技术路线
原文未明确说明

## 6. 实验设置
原文未明确说明

## 7. 数据集与评价指标
原文未明确说明

## 8. 主要实验结果
原文未明确说明

## 9. 创新点总结
测试创新点。

## 10. 局限性分析
原文未明确说明

## 11. 对相关课题的启发
原文未明确说明

## 12. 可引用表述
原文未明确说明

## 13. BibTeX
原文未明确说明
"""


def _create_parsed_json(metadata_dir: str, paper_id: str) -> str:
    data = {
        "paper_id": paper_id,
        "title": "A Novel Approach to Infrared Small Target Detection",
        "abstract": "This paper presents a novel approach to infrared small target detection.",
        "sections": [
            {
                "heading": "Introduction",
                "content": "Infrared small target detection is critical.",
            },
            {
                "heading": "Method",
                "content": "Our method uses VLM with spatial attention.",
            },
            {"heading": "Experiments", "content": "We evaluate on SIRST dataset."},
            {
                "heading": "Conclusion",
                "content": "We present a novel VLM-based approach.",
            },
        ],
        "full_text": "A Novel Approach to Infrared Small Target Detection\n\nAbstract\nThis paper presents...\n\nIntroduction\nInfrared small target detection is critical...\n\nMethod\nOur method uses VLM...\n\nExperiments\nWe evaluate on SIRST...\n\nConclusion\nWe present a novel approach...",
    }
    os.makedirs(metadata_dir, exist_ok=True)
    filepath = os.path.join(metadata_dir, f"{paper_id}_parsed.json")
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False)
    return filepath


def test_build_note_prompt():
    prompt = build_note_prompt("Test Title", "Test content")
    assert "Test Title" in prompt
    assert "Test content" in prompt
    assert "## 1. 基本信息" in prompt
    assert "## 13. BibTeX" in prompt
    assert "不要编造论文中没有的信息" in prompt
    assert "原文未明确说明" in prompt
    assert "Markdown 模板" in prompt


def test_build_paper_content_short():
    parsed = {
        "abstract": "Short abstract.",
        "sections": [],
        "full_text": "A short paper with minimal content.",
    }
    content = _build_paper_content(parsed)
    assert "A short paper" in content


def test_build_paper_content_long_truncates():
    long_text = "x " * 9000
    parsed = {
        "abstract": "Abstract here.",
        "sections": [
            {"heading": "Intro", "content": long_text},
        ],
        "full_text": long_text,
    }
    content = _build_paper_content(parsed)
    assert len(content) <= 8100
    assert "内容过长" in content


def test_load_parsed_json():
    with tempfile.TemporaryDirectory() as tmpdir:
        _create_parsed_json(tmpdir, "paper_test")
        data = load_parsed_result("paper_test", tmpdir)
        assert data["paper_id"] == "paper_test"
        assert data["title"]


def test_load_parsed_json_not_found():
    with tempfile.TemporaryDirectory() as tmpdir:
        try:
            load_parsed_result("paper_nonexistent", tmpdir)
            assert False, "Should have raised"
        except FileNotFoundError:
            pass


def test_save_markdown():
    with tempfile.TemporaryDirectory() as tmpdir:
        filepath = save_markdown("paper_test", "# Hello\nTest", tmpdir)
        assert os.path.exists(filepath)
        assert filepath.endswith("paper_test_note.md")
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()
        assert "# Hello" in content


def test_save_markdown_overwrite():
    with tempfile.TemporaryDirectory() as tmpdir:
        save_markdown("paper_test", "v1", tmpdir)
        save_markdown("paper_test", "v2", tmpdir)
        filepath = os.path.join(tmpdir, "paper_test_note.md")
        with open(filepath, "r", encoding="utf-8") as f:
            assert f.read() == "v2"


def test_generate_note_with_mock_llm():
    with tempfile.TemporaryDirectory() as tmpdir:
        _create_parsed_json(tmpdir, "paper_mock")

        mock_llm = MagicMock()
        mock_llm.generate_text.return_value = MOCK_MARKDOWN

        result = generate_note("paper_mock", metadata_dir=tmpdir, llm_client=mock_llm)

        assert "论文阅读笔记" in result
        assert "红外小目标检测" in result
        assert "## 1. 基本信息" in result
        assert "## 13. BibTeX" in result

        mock_llm.generate_text.assert_called_once()
        call_args = mock_llm.generate_text.call_args[0][0]
        assert "Infrared Small Target Detection" in call_args
        assert "## 13. BibTeX" in call_args


def test_generate_note_missing_json():
    with tempfile.TemporaryDirectory() as tmpdir:
        mock_llm = MagicMock()
        try:
            generate_note("paper_nonexistent", metadata_dir=tmpdir, llm_client=mock_llm)
            assert False, "Should have raised"
        except FileNotFoundError:
            pass
        mock_llm.generate_text.assert_not_called()


if __name__ == "__main__":
    test_build_note_prompt()
    test_build_paper_content_short()
    test_build_paper_content_long_truncates()
    test_load_parsed_json()
    test_load_parsed_json_not_found()
    test_save_markdown()
    test_save_markdown_overwrite()
    test_generate_note_with_mock_llm()
    test_generate_note_missing_json()
    print("All tests passed.")
