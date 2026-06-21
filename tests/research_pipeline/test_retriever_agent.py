"""
Tests for Retriever Agent

验证 Retriever Agent 的 source routing、candidate persistence 和 degraded mode。
"""

import sqlite3
from pathlib import Path

import pytest

from app.research_pipeline import store
from app.research_pipeline.agents.retriever import RetrieverAgent
from app.research_pipeline.schemas import PaperCandidate


# ==================== Fixtures ====================


@pytest.fixture
def temp_db(tmp_path: Path) -> str:
    """创建临时测试数据库"""
    db_path = str(tmp_path / "test_retriever.db")
    store.init_db(db_path)
    return db_path


@pytest.fixture
def sample_run_id(temp_db: str) -> str:
    """创建一个测试 run"""
    run_id = store.create_run(
        db_path=temp_db,
        question="What are the latest advances in transformer models?",
        source_mode="web_search",
        max_reader_papers=8,
        reader_concurrency=3,
    )
    return run_id


# ==================== Fake Source Adapters ====================


class FakeSemanticScholarAdapter:
    """Fake Semantic Scholar adapter that returns mock results"""

    def search(self, query: str, limit: int = 10) -> list[PaperCandidate]:
        return [
            PaperCandidate(
                paper_id="ss_paper_1",
                source="semantic_scholar",
                title="Attention Is All You Need",
                authors=["Vaswani", "Shazeer"],
                year=2017,
                venue="NeurIPS",
                abstract="We propose a new architecture...",
                doi="10.1000/example1",
                arxiv_id="1706.03762",
                semantic_scholar_id="ss_paper_1",
                citation_count=50000,
            ),
            PaperCandidate(
                paper_id="ss_paper_2",
                source="semantic_scholar",
                title="BERT: Pre-training of Deep Bidirectional Transformers",
                authors=["Devlin", "Chang"],
                year=2019,
                venue="NAACL",
                doi="10.1000/example2",
                semantic_scholar_id="ss_paper_2",
                citation_count=30000,
            ),
        ]


class FakeArxivAdapter:
    """Fake arXiv adapter that returns mock results"""

    def search(self, query: str, max_results: int = 10) -> list[PaperCandidate]:
        return [
            PaperCandidate(
                paper_id="2103.12345",
                source="arxiv",
                title="Scaling Language Models: Methods and Analysis",
                authors=["Smith", "Johnson"],
                year=2021,
                abstract="We study scaling laws...",
                arxiv_id="2103.12345",
                pdf_url="https://arxiv.org/pdf/2103.12345.pdf",
            ),
        ]


class FakeZoteroAdapter:
    """Fake Zotero adapter that returns mock results"""

    def get_candidates(self, collection_key: str) -> list[PaperCandidate]:
        return [
            PaperCandidate(
                paper_id="zotero_item_1",
                source="zotero",
                title="Attention Is All You Need",
                authors=["Vaswani", "Shazeer"],
                year=2017,
                venue="NeurIPS",
                doi="10.1000/example1",
                arxiv_id="1706.03762",
                zotero_item_id="zotero_item_1",
                local_pdf_path="/path/to/attention.pdf",
            ),
            PaperCandidate(
                paper_id="zotero_item_2",
                source="zotero",
                title="Transformers in Vision",
                authors=["Dosovitskiy"],
                year=2021,
                doi="10.1000/example3",
                zotero_item_id="zotero_item_2",
                local_pdf_path="/path/to/vit.pdf",
            ),
        ]


class FailingSemanticScholarAdapter:
    """Fake adapter that raises an exception"""

    def search(self, query: str, limit: int = 10) -> list[PaperCandidate]:
        raise RuntimeError("Semantic Scholar API timeout")


class FailingArxivAdapter:
    """Fake adapter that raises an exception"""

    def search(self, query: str, max_results: int = 10) -> list[PaperCandidate]:
        raise RuntimeError("arXiv API unavailable")


# ==================== Tests ====================


def test_web_search_mode_calls_both_sources(temp_db: str, sample_run_id: str) -> None:
    """
    验收标准: web_search 调用 Semantic Scholar 和 arXiv
    """
    agent = RetrieverAgent(
        db_path=temp_db,
        run_id=sample_run_id,
        semantic_scholar_adapter=FakeSemanticScholarAdapter(),
        arxiv_adapter=FakeArxivAdapter(),
        zotero_adapter=None,
    )

    agent.execute()

    # 检查候选论文是否持久化
    candidates = store.get_candidates(temp_db, sample_run_id)

    # 应该有 3 篇论文：2 篇来自 SS，1 篇来自 arXiv
    # 但有重复的 "Attention Is All You Need"（ss_paper_1 和没有匹配的）
    # 去重后应该有 3 篇
    assert len(candidates) == 3

    # 检查来源
    sources = {c["source"] for c in candidates}
    assert "semantic_scholar" in sources
    assert "arxiv" in sources

    # 检查标题
    titles = {c["title"] for c in candidates}
    assert "Attention Is All You Need" in titles
    assert "BERT: Pre-training of Deep Bidirectional Transformers" in titles
    assert "Scaling Language Models: Methods and Analysis" in titles


def test_zotero_only_mode_calls_zotero_only(temp_db: str) -> None:
    """
    验收标准: zotero_only 只调用 Zotero
    """
    run_id = store.create_run(
        db_path=temp_db,
        question="Test question",
        source_mode="zotero_only",
        zotero_collection_key="ABC123",
        max_reader_papers=8,
        reader_concurrency=3,
    )

    agent = RetrieverAgent(
        db_path=temp_db,
        run_id=run_id,
        semantic_scholar_adapter=FakeSemanticScholarAdapter(),
        arxiv_adapter=FakeArxivAdapter(),
        zotero_adapter=FakeZoteroAdapter(),
    )

    agent.execute()

    # 检查候选论文
    candidates = store.get_candidates(temp_db, run_id)

    # 应该只有 Zotero 的 2 篇论文
    assert len(candidates) == 2

    # 所有候选论文都应该来自 Zotero
    for candidate in candidates:
        assert candidate["source"] == "zotero"

    # 检查标题
    titles = {c["title"] for c in candidates}
    assert "Attention Is All You Need" in titles
    assert "Transformers in Vision" in titles


def test_hybrid_mode_preserves_zotero_seed_and_merges_web_search(temp_db: str) -> None:
    """
    验收标准: hybrid 先保留 Zotero seed，再合并 Web Search
    """
    run_id = store.create_run(
        db_path=temp_db,
        question="Test question",
        source_mode="hybrid",
        zotero_collection_key="ABC123",
        max_reader_papers=8,
        reader_concurrency=3,
    )

    agent = RetrieverAgent(
        db_path=temp_db,
        run_id=run_id,
        semantic_scholar_adapter=FakeSemanticScholarAdapter(),
        arxiv_adapter=FakeArxivAdapter(),
        zotero_adapter=FakeZoteroAdapter(),
    )

    agent.execute()

    # 检查候选论文
    candidates = store.get_candidates(temp_db, run_id)

    # Zotero: 2 篇 (Attention, Transformers in Vision)
    # SS: 2 篇 (Attention 重复, BERT)
    # arXiv: 1 篇 (Scaling)
    # 去重后: Attention (zotero + SS 合并), Transformers in Vision (zotero), BERT (SS), Scaling (arXiv)
    # = 4 篇
    assert len(candidates) == 4

    # 检查来源分布
    sources = [c["source"] for c in candidates]
    assert "zotero" in sources
    assert "semantic_scholar" in sources
    assert "arxiv" in sources

    # 检查重复论文的合并
    attention_paper = next(c for c in candidates if "Attention Is All You Need" in c["title"])
    # 应该保留 Zotero 作为主要来源（优先级最高）
    assert attention_paper["source"] == "zotero"
    # 但应该合并 SS 的 semantic_scholar_id
    assert attention_paper["semantic_scholar_id"] == "ss_paper_1"


def test_source_failure_writes_event_and_allows_degraded(temp_db: str, sample_run_id: str) -> None:
    """
    验收标准: source 失败会写 event 并允许 run degraded
    """
    agent = RetrieverAgent(
        db_path=temp_db,
        run_id=sample_run_id,
        semantic_scholar_adapter=FailingSemanticScholarAdapter(),
        arxiv_adapter=FakeArxivAdapter(),
        zotero_adapter=None,
    )

    # 执行应该成功（degraded mode）
    agent.execute()

    # 检查 stage 状态
    run_detail = store.get_run_detail(temp_db, sample_run_id)
    retriever_stage = next(s for s in run_detail["stages"] if s["stage"] == "retriever")
    assert retriever_stage["status"] == "degraded"

    # 检查事件日志
    events = run_detail["events"]
    error_events = [e for e in events if e["level"] == "error"]
    assert len(error_events) >= 1

    # 验证错误事件消息
    ss_error = next(e for e in error_events if "Semantic Scholar" in e["message"])
    assert "timeout" in ss_error["message"].lower() or "failed" in ss_error["message"].lower()

    # 应该仍有 arXiv 的候选论文
    candidates = store.get_candidates(temp_db, sample_run_id)
    assert len(candidates) >= 1
    assert any(c["source"] == "arxiv" for c in candidates)


def test_all_sources_fail_marks_stage_as_failed(temp_db: str, sample_run_id: str) -> None:
    """
    验证: 当所有 source 都失败时，stage 标记为 failed
    """
    agent = RetrieverAgent(
        db_path=temp_db,
        run_id=sample_run_id,
        semantic_scholar_adapter=FailingSemanticScholarAdapter(),
        arxiv_adapter=FailingArxivAdapter(),
        zotero_adapter=None,
    )

    # 执行应该抛出异常
    with pytest.raises(RuntimeError, match="All sources failed"):
        agent.execute()

    # 检查 stage 状态
    run_detail = store.get_run_detail(temp_db, sample_run_id)
    retriever_stage = next(s for s in run_detail["stages"] if s["stage"] == "retriever")
    assert retriever_stage["status"] == "failed"


def test_candidates_visible_via_get_run_detail(temp_db: str, sample_run_id: str) -> None:
    """
    验收标准: 候选论文可通过 GET /research-pipeline/runs/{run_id} 查看
    """
    agent = RetrieverAgent(
        db_path=temp_db,
        run_id=sample_run_id,
        semantic_scholar_adapter=FakeSemanticScholarAdapter(),
        arxiv_adapter=FakeArxivAdapter(),
        zotero_adapter=None,
    )

    agent.execute()

    # 使用 get_run_detail 获取完整信息
    run_detail = store.get_run_detail(temp_db, sample_run_id)

    # 检查 candidates 字段
    assert "candidates" in run_detail
    assert len(run_detail["candidates"]) > 0

    # 验证 candidate 结构
    first_candidate = run_detail["candidates"][0]
    assert "paper_id" in first_candidate
    assert "source" in first_candidate
    assert "title" in first_candidate
    assert "authors" in first_candidate


def test_deduplication_happens_before_persistence(temp_db: str) -> None:
    """
    验证: 去重发生在持久化之前
    """
    run_id = store.create_run(
        db_path=temp_db,
        question="Test question",
        source_mode="hybrid",
        zotero_collection_key="ABC123",
        max_reader_papers=8,
        reader_concurrency=3,
    )

    agent = RetrieverAgent(
        db_path=temp_db,
        run_id=run_id,
        semantic_scholar_adapter=FakeSemanticScholarAdapter(),
        arxiv_adapter=FakeArxivAdapter(),
        zotero_adapter=FakeZoteroAdapter(),
    )

    agent.execute()

    # Zotero 和 SS 都有 "Attention Is All You Need"
    # 去重后应该只有 1 条记录
    candidates = store.get_candidates(temp_db, run_id)
    attention_papers = [c for c in candidates if "Attention Is All You Need" in c["title"]]
    assert len(attention_papers) == 1
