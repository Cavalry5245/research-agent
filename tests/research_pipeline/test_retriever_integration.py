"""
Integration test for Retriever Agent with Runner

验证 runner 能够正确调用 RetrieverAgent。
"""

from pathlib import Path
from typing import Any

import pytest

from app.research_pipeline import store
from app.research_pipeline.runner import PipelineRunner, create_default_agent
from app.research_pipeline.schemas import PaperCandidate


# ==================== Fake Adapters ====================


class FakeSemanticScholarAdapter:
    """Fake adapter for testing"""

    def search(self, query: str, limit: int = 10) -> list[PaperCandidate]:
        return [
            PaperCandidate(
                paper_id="ss_1",
                source="semantic_scholar",
                title="Test Paper from SS",
                authors=["Author A"],
                year=2023,
            )
        ]


class FakeArxivAdapter:
    """Fake adapter for testing"""

    def search(self, query: str, max_results: int = 10) -> list[PaperCandidate]:
        return [
            PaperCandidate(
                paper_id="arxiv_1",
                source="arxiv",
                title="Test Paper from arXiv",
                authors=["Author B"],
                year=2023,
            )
        ]


# ==================== Fixtures ====================


@pytest.fixture
def temp_db(tmp_path: Path) -> str:
    """创建临时测试数据库"""
    db_path = str(tmp_path / "test_integration.db")
    store.init_db(db_path)
    return db_path


@pytest.fixture
def sample_run_id(temp_db: str) -> str:
    """创建一个测试 run"""
    run_id = store.create_run(
        db_path=temp_db,
        question="What are transformers?",
        source_mode="web_search",
        max_reader_papers=8,
        reader_concurrency=3,
    )
    return run_id


# ==================== Tests ====================


def test_runner_creates_retriever_agent(temp_db: str, sample_run_id: str) -> None:
    """
    验证 runner 能够创建 RetrieverAgent 并执行 retriever stage
    """

    def test_agent_factory(stage: str, db_path: str, run_id: str) -> Any:
        """测试用 agent factory，注入 fake adapters"""
        if stage == "retriever":
            from app.research_pipeline.agents.retriever import RetrieverAgent

            return RetrieverAgent(
                db_path=db_path,
                run_id=run_id,
                semantic_scholar_adapter=FakeSemanticScholarAdapter(),
                arxiv_adapter=FakeArxivAdapter(),
                zotero_adapter=None,
            )
        else:
            from app.research_pipeline.runner import StubAgent

            return StubAgent(stage, db_path, run_id)

    # 创建 runner
    runner = PipelineRunner(db_path=temp_db, agent_factory=test_agent_factory)

    # 执行单个 stage
    runner._execute_stage(sample_run_id, "retriever")

    # 验证 stage 状态
    run_detail = store.get_run_detail(temp_db, sample_run_id)
    retriever_stage = next(s for s in run_detail["stages"] if s["stage"] == "retriever")
    assert retriever_stage["status"] == "completed"

    # 验证候选论文被持久化
    candidates = store.get_candidates(temp_db, sample_run_id)
    assert len(candidates) == 2

    titles = {c["title"] for c in candidates}
    assert "Test Paper from SS" in titles
    assert "Test Paper from arXiv" in titles


def test_default_agent_factory_creates_retriever_agent(temp_db: str, sample_run_id: str) -> None:
    """
    验证 create_default_agent 能够创建 RetrieverAgent
    """
    agent = create_default_agent("retriever", temp_db, sample_run_id)

    from app.research_pipeline.agents.retriever import RetrieverAgent

    assert isinstance(agent, RetrieverAgent)
    assert agent.db_path == temp_db
    assert agent.run_id == sample_run_id


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
