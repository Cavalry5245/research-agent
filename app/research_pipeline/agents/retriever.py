"""
Retriever Agent

根据 source_mode 调用来源 adapter，写入 candidates，并执行候选集排序。
"""

from typing import Any

from app.research_pipeline import events, store
from app.research_pipeline.schemas import PaperCandidate
from app.research_pipeline.sources.arxiv import ArxivSourceAdapter
from app.research_pipeline.sources.normalizer import deduplicate_candidates
from app.research_pipeline.sources.semantic_scholar import SemanticScholarSourceAdapter
from app.research_pipeline.sources.zotero import ZoteroSourceAdapter


class RetrieverAgent:
    """
    Retriever Agent that orchestrates paper retrieval across sources.

    Responsibilities:
    - Route to appropriate sources based on source_mode
    - Normalize and deduplicate candidates
    - Handle source failures gracefully (degraded mode)
    - Persist candidates to database
    """

    def __init__(
        self,
        db_path: str,
        run_id: str,
        semantic_scholar_adapter: SemanticScholarSourceAdapter | None = None,
        arxiv_adapter: ArxivSourceAdapter | None = None,
        zotero_adapter: ZoteroSourceAdapter | None = None,
    ):
        """
        初始化 Retriever Agent。

        Args:
            db_path: 数据库路径
            run_id: Run ID
            semantic_scholar_adapter: Semantic Scholar adapter（可注入 fake 用于测试）
            arxiv_adapter: arXiv adapter（可注入 fake 用于测试）
            zotero_adapter: Zotero adapter（可注入 fake 用于测试）
        """
        self.db_path = db_path
        self.run_id = run_id
        self.semantic_scholar_adapter = semantic_scholar_adapter
        self.arxiv_adapter = arxiv_adapter
        self.zotero_adapter = zotero_adapter

    def execute(self) -> dict[str, Any]:
        """
        执行 retriever stage 逻辑。

        Returns:
            字典包含 stage 结果（candidates_found, candidates_selected 等）

        Raises:
            RuntimeError: 当所有 source 都失败时
        """
        # 写入 start event
        events.write_stage_start_event(
            db_path=self.db_path,
            run_id=self.run_id,
            stage="retriever",
        )

        # 获取 run 配置
        run_detail = store.get_run_detail(self.db_path, self.run_id)
        if run_detail is None:
            raise RuntimeError(f"Run {self.run_id} not found")

        source_mode = run_detail["source_mode"]
        zotero_collection_key = run_detail["zotero_collection_key"]
        question = run_detail["question"]

        # 根据 source_mode 调用相应的 adapter
        all_candidates: list[PaperCandidate] = []
        source_failures: list[str] = []

        if source_mode == "web_search":
            all_candidates.extend(self._search_web_sources(question, source_failures))

        elif source_mode == "zotero_only":
            all_candidates.extend(
                self._search_zotero_source(zotero_collection_key, source_failures)
            )

        elif source_mode == "hybrid":
            # 先获取 Zotero seed papers
            zotero_candidates = self._search_zotero_source(
                zotero_collection_key, source_failures
            )
            all_candidates.extend(zotero_candidates)

            # 再获取 Web Search papers
            web_candidates = self._search_web_sources(question, source_failures)
            all_candidates.extend(web_candidates)

        else:
            raise ValueError(f"Unknown source_mode: {source_mode}")

        # 检查是否所有 source 都失败
        if not all_candidates:
            error_msg = f"All sources failed: {', '.join(source_failures)}"
            events.write_stage_error_event(
                db_path=self.db_path,
                run_id=self.run_id,
                stage="retriever",
                message=error_msg,
            )
            store.update_stage(
                db_path=self.db_path,
                run_id=self.run_id,
                stage="retriever",
                status="failed",
                error=error_msg,
            )
            raise RuntimeError(error_msg)

        # 去重
        events.write_stage_progress_event(
            db_path=self.db_path,
            run_id=self.run_id,
            stage="retriever",
            message=f"Deduplicating {len(all_candidates)} candidates",
            payload={"action": "deduplicate", "before_count": len(all_candidates)},
        )

        deduplicated = deduplicate_candidates(all_candidates)

        events.write_stage_progress_event(
            db_path=self.db_path,
            run_id=self.run_id,
            stage="retriever",
            message=f"Deduplicated to {len(deduplicated)} unique candidates",
            payload={"action": "deduplicate", "after_count": len(deduplicated)},
        )

        # 持久化到数据库
        events.write_stage_progress_event(
            db_path=self.db_path,
            run_id=self.run_id,
            stage="retriever",
            message="Persisting candidates to database",
            payload={"action": "persist", "count": len(deduplicated)},
        )

        for candidate in deduplicated:
            store.create_candidate(
                db_path=self.db_path,
                run_id=self.run_id,
                candidate=candidate,
            )

        # 确定最终 stage 状态
        final_status = "degraded" if source_failures else "completed"
        result = {
            "candidates_found": len(deduplicated),
            "source_failures": source_failures,
        }

        # 写入 completion event
        events.write_stage_complete_event(
            db_path=self.db_path,
            run_id=self.run_id,
            stage="retriever",
            payload=result,
        )

        # 更新 stage 状态
        store.update_stage(
            db_path=self.db_path,
            run_id=self.run_id,
            stage="retriever",
            status=final_status,
            progress=1.0,
            message=f"Retrieved {len(deduplicated)} candidates",
        )

        return result

    def _search_web_sources(
        self, query: str, failures: list[str]
    ) -> list[PaperCandidate]:
        """
        搜索 Web sources (Semantic Scholar + arXiv)。

        Args:
            query: 搜索查询
            failures: 失败列表（会被修改）

        Returns:
            候选论文列表
        """
        candidates = []

        # Semantic Scholar
        candidates.extend(self._search_semantic_scholar(query, failures))

        # arXiv
        candidates.extend(self._search_arxiv(query, failures))

        return candidates

    def _search_semantic_scholar(
        self, query: str, failures: list[str]
    ) -> list[PaperCandidate]:
        """
        搜索 Semantic Scholar。

        Args:
            query: 搜索查询
            failures: 失败列表（会被修改）

        Returns:
            候选论文列表
        """
        try:
            events.write_stage_progress_event(
                db_path=self.db_path,
                run_id=self.run_id,
                stage="retriever",
                message="Searching Semantic Scholar",
                payload={"action": "search", "source": "semantic_scholar"},
            )

            if self.semantic_scholar_adapter is None:
                raise RuntimeError("Semantic Scholar adapter is not initialized")

            candidates = self.semantic_scholar_adapter.search(query=query, limit=10)

            events.write_stage_progress_event(
                db_path=self.db_path,
                run_id=self.run_id,
                stage="retriever",
                message=f"Found {len(candidates)} papers from Semantic Scholar",
                payload={
                    "action": "search_result",
                    "source": "semantic_scholar",
                    "count": len(candidates),
                },
            )

            return candidates

        except Exception as e:
            error_msg = f"Semantic Scholar search failed: {type(e).__name__}: {str(e)}"
            events.write_stage_error_event(
                db_path=self.db_path,
                run_id=self.run_id,
                stage="retriever",
                message=error_msg,
                payload={"source": "semantic_scholar"},
            )
            failures.append("semantic_scholar")
            return []

    def _search_arxiv(self, query: str, failures: list[str]) -> list[PaperCandidate]:
        """
        搜索 arXiv。

        Args:
            query: 搜索查询
            failures: 失败列表（会被修改）

        Returns:
            候选论文列表
        """
        try:
            events.write_stage_progress_event(
                db_path=self.db_path,
                run_id=self.run_id,
                stage="retriever",
                message="Searching arXiv",
                payload={"action": "search", "source": "arxiv"},
            )

            if self.arxiv_adapter is None:
                raise RuntimeError("arXiv adapter is not initialized")

            candidates = self.arxiv_adapter.search(query=query, max_results=10)

            events.write_stage_progress_event(
                db_path=self.db_path,
                run_id=self.run_id,
                stage="retriever",
                message=f"Found {len(candidates)} papers from arXiv",
                payload={
                    "action": "search_result",
                    "source": "arxiv",
                    "count": len(candidates),
                },
            )

            return candidates

        except Exception as e:
            error_msg = f"arXiv search failed: {type(e).__name__}: {str(e)}"
            events.write_stage_error_event(
                db_path=self.db_path,
                run_id=self.run_id,
                stage="retriever",
                message=error_msg,
                payload={"source": "arxiv"},
            )
            failures.append("arxiv")
            return []

    def _search_zotero_source(
        self, collection_key: str | None, failures: list[str]
    ) -> list[PaperCandidate]:
        """
        从 Zotero 获取 seed papers。

        Args:
            collection_key: Zotero collection key
            failures: 失败列表（会被修改）

        Returns:
            候选论文列表
        """
        try:
            if collection_key is None:
                raise ValueError("Zotero collection key is required for this source mode")

            events.write_stage_progress_event(
                db_path=self.db_path,
                run_id=self.run_id,
                stage="retriever",
                message=f"Fetching papers from Zotero collection {collection_key}",
                payload={"action": "search", "source": "zotero"},
            )

            if self.zotero_adapter is None:
                raise RuntimeError("Zotero adapter is not initialized")

            candidates = self.zotero_adapter.get_candidates(collection_key)

            events.write_stage_progress_event(
                db_path=self.db_path,
                run_id=self.run_id,
                stage="retriever",
                message=f"Found {len(candidates)} papers from Zotero",
                payload={
                    "action": "search_result",
                    "source": "zotero",
                    "count": len(candidates),
                },
            )

            return candidates

        except Exception as e:
            error_msg = f"Zotero fetch failed: {type(e).__name__}: {str(e)}"
            events.write_stage_error_event(
                db_path=self.db_path,
                run_id=self.run_id,
                stage="retriever",
                message=error_msg,
                payload={"source": "zotero"},
            )
            failures.append("zotero")
            return []
