"""测试父文档回填逻辑"""
import os
import sys
import tempfile
from unittest.mock import MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.schemas import Chunk, ParentDocument
from app.services.paper_qa import _build_context, answer_question
from app.services.parent_doc_store import ParentDocumentStore
from app.services.vector_backends.json_backend import JsonVectorBackend
from app.services.vector_store import VectorStore


def test_build_context_with_parent_documents():
    """测试使用父文档构建上下文"""
    parent1 = ParentDocument(
        parent_id="parent_001",
        paper_id="paper_A",
        title="Test Paper A",
        section_path="Section 1 / Subsection 1.1",
        content="Complete parent document content for section 1.1. This is much longer than child chunks.",
        page_range="2-3",
        element_type="section",
    )

    parent2 = ParentDocument(
        parent_id="parent_002",
        paper_id="paper_A",
        title="Test Paper A",
        section_path="Section 2 / Subsection 2.1",
        content="Complete parent document content for section 2.1.",
        page_range="5-6",
        element_type="section",
    )

    results = [
        {
            "paper_id": "paper_A",
            "title": "Test Paper A",
            "section": "Section 1",
            "content": "Child chunk 1",
            "chunk_id": "chunk_001",
            "parent_id": "parent_001",
            "parent_document": parent1,
        },
        {
            "paper_id": "paper_A",
            "title": "Test Paper A",
            "section": "Section 1",
            "content": "Child chunk 2",
            "chunk_id": "chunk_002",
            "parent_id": "parent_001",
            "parent_document": parent1,
        },
        {
            "paper_id": "paper_A",
            "title": "Test Paper A",
            "section": "Section 2",
            "content": "Child chunk 3",
            "chunk_id": "chunk_003",
            "parent_id": "parent_002",
            "parent_document": parent2,
        },
    ]

    ctx = _build_context(results)

    # 验证使用父文档内容
    assert "Complete parent document content for section 1.1" in ctx
    assert "Complete parent document content for section 2.1" in ctx

    # 验证子块内容不在上下文中（被父文档替换）
    assert "Child chunk 1" not in ctx
    assert "Child chunk 2" not in ctx
    assert "Child chunk 3" not in ctx

    # 验证引用格式
    assert "[paper_A p.2-3 Section 1 / Subsection 1.1]" in ctx
    assert "[paper_A p.5-6 Section 2 / Subsection 2.1]" in ctx

    # 验证分隔符
    assert "---" in ctx

    # 验证父文档去重：parent_001 出现两次，但只应该在上下文中出现一次
    assert ctx.count("Complete parent document content for section 1.1") == 1


def test_build_context_without_parent_documents():
    """测试向后兼容：无父文档时使用子块"""
    results = [
        {
            "paper_id": "paper_B",
            "title": "Test Paper B",
            "section": "Introduction",
            "content": "Child chunk without parent",
            "chunk_id": "chunk_004",
            "page_number": 1,
        },
    ]

    ctx = _build_context(results)

    # 验证使用子块内容
    assert "Child chunk without parent" in ctx

    # 验证引用格式
    assert "[paper_B p.1 Introduction]" in ctx


def test_answer_question_with_parent_backfill():
    """测试 answer_question 的父文档回填逻辑"""
    with tempfile.TemporaryDirectory() as tmpdir:
        # 初始化 vector store
        path = os.path.join(tmpdir, "vectors")
        store = VectorStore(persist_dir=path, backend=JsonVectorBackend(path))

        # 初始化 parent store
        parent_store = ParentDocumentStore(persist_dir=os.path.join(tmpdir, "parents"))

        # 添加父文档
        parent = ParentDocument(
            parent_id="parent_test_001",
            paper_id="paper_test",
            title="Test Paper",
            section_path="Method / Architecture",
            content="Complete method description with full context. This is the parent document content that provides complete information.",
            page_range="3-4",
            element_type="section",
        )
        parent_store.add_parents("paper_test", [parent])

        # 添加子块到 vector store，带有 parent_id
        chunks = [
            Chunk(
                chunk_id="paper_test_chunk_0001",
                paper_id="paper_test",
                title="Test Paper",
                section="Method",
                content="Child chunk 1 partial content",
                parent_id="parent_test_001",
                section_path="Method / Architecture",
                page_range="3-4",
            ),
            Chunk(
                chunk_id="paper_test_chunk_0002",
                paper_id="paper_test",
                title="Test Paper",
                section="Method",
                content="Child chunk 2 partial content",
                parent_id="parent_test_001",
                section_path="Method / Architecture",
                page_range="3-4",
            ),
        ]
        chunks[0].page_number = 3
        chunks[1].page_number = 4

        embeddings = [[0.5, 0.5], [0.6, 0.4]]
        store.add_chunks(chunks, embeddings)

        # Mock 客户端
        mock_emb = MagicMock()
        mock_emb.embed_query.return_value = [0.55, 0.45]

        mock_llm = MagicMock()
        mock_llm.generate_text.return_value = "基于完整上下文的答案"

        # 执行 QA
        result = answer_question(
            question="方法是什么？",
            vector_store=store,
            embedding_client=mock_emb,
            llm_client=mock_llm,
            top_k=2,
            parent_store=parent_store,  # Pass the test parent_store
        )

        # 验证 prompt 包含父文档内容
        call_prompt = mock_llm.generate_text.call_args[0][0]
        assert "Complete method description with full context" in call_prompt
        assert "This is the parent document content" in call_prompt

        # 验证父文档去重（两个子块共享同一父文档，只应出现一次）
        assert call_prompt.count("Complete method description with full context") == 1

        # 验证子块内容不在 prompt 中
        assert "Child chunk 1 partial content" not in call_prompt
        assert "Child chunk 2 partial content" not in call_prompt

        # 验证 sources 包含 parent_id 和新字段
        assert len(result["sources"]) == 2
        for source in result["sources"]:
            assert source["parent_id"] == "parent_test_001"
            assert source["section_path"] == "Method / Architecture"
            assert source["page_range"] == "3-4"
            assert source["element_type"] is None or source["element_type"] == "section"


def test_answer_question_backward_compatibility():
    """测试向后兼容：没有 parent_id 的旧数据"""
    with tempfile.TemporaryDirectory() as tmpdir:
        path = os.path.join(tmpdir, "vectors")
        store = VectorStore(persist_dir=path, backend=JsonVectorBackend(path))

        # 添加旧格式的 chunks（无 parent_id）
        chunks = [
            Chunk(
                chunk_id="old_chunk_001",
                paper_id="old_paper",
                title="Old Paper",
                section="Results",
                content="Old chunk without parent_id",
            ),
        ]
        chunks[0].page_number = 5

        store.add_chunks(chunks, [[0.7, 0.3]])

        mock_emb = MagicMock()
        mock_emb.embed_query.return_value = [0.7, 0.3]

        mock_llm = MagicMock()
        mock_llm.generate_text.return_value = "基于旧数据的答案"

        result = answer_question(
            question="结果是什么？",
            vector_store=store,
            embedding_client=mock_emb,
            llm_client=mock_llm,
            top_k=1,
        )

        # 验证使用子块内容
        call_prompt = mock_llm.generate_text.call_args[0][0]
        assert "Old chunk without parent_id" in call_prompt

        # 验证 sources 中 parent_id 为 None
        assert len(result["sources"]) == 1
        assert result["sources"][0]["parent_id"] is None


if __name__ == "__main__":
    test_build_context_with_parent_documents()
    test_build_context_without_parent_documents()
    test_answer_question_with_parent_backfill()
    test_answer_question_backward_compatibility()
    print("All parent backfill tests passed!")
