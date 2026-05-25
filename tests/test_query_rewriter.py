import os
import sys
from unittest.mock import MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.services.query_rewriter import QueryRewriter


def test_query_rewriter_returns_llm_output():
    llm = MagicMock()
    llm.generate_text.return_value = "深度学习在医学影像分割中的应用"
    rw = QueryRewriter(llm)

    out = rw.rewrite("医学图像分割怎么做")

    assert out == "深度学习在医学影像分割中的应用"
    llm.generate_text.assert_called_once()


def test_query_rewriter_falls_back_to_original_on_empty_llm_output():
    llm = MagicMock()
    llm.generate_text.return_value = "   "
    rw = QueryRewriter(llm)

    assert rw.rewrite("原始查询") == "原始查询"


def test_query_rewriter_falls_back_on_llm_exception():
    llm = MagicMock()
    llm.generate_text.side_effect = RuntimeError("LLM down")
    rw = QueryRewriter(llm)

    assert rw.rewrite("原始查询") == "原始查询"


def test_query_rewriter_passes_through_empty_input():
    llm = MagicMock()
    rw = QueryRewriter(llm)
    assert rw.rewrite("") == ""
    assert rw.rewrite("   ") == "   "
    llm.generate_text.assert_not_called()


def test_query_rewriter_keeps_only_first_line():
    llm = MagicMock()
    llm.generate_text.return_value = "改写后的第一行\n解释：因为...\n备注"
    rw = QueryRewriter(llm)

    assert rw.rewrite("q") == "改写后的第一行"
