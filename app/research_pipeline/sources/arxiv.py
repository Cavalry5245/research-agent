"""
arXiv Source Adapter

将 arXiv search 集成到 research pipeline，提供论文搜索和 candidate 归一化能力。
"""

from app.research_pipeline.schemas import PaperCandidate
from app.research_pipeline.sources.normalizer import normalize_arxiv_paper
from app.research_workflow.arxiv_mcp_adapter import ArxivMCPAdapter


class ArxivSourceAdapter:
    """
    arXiv source adapter for research pipeline.

    Provides paper search and candidate normalization from arXiv.
    """

    def __init__(self, client: ArxivMCPAdapter | None = None) -> None:
        """
        初始化 arXiv source adapter。

        Args:
            client: ArxivMCPAdapter 实例。如果为 None，使用默认配置。
                   支持注入 fake client 用于测试（无网络调用）。
        """
        self.client = client

    def search(self, query: str, max_results: int = 10) -> list[PaperCandidate]:
        """
        搜索 arXiv 论文并返回归一化的候选论文。

        Args:
            query: 搜索查询字符串
            max_results: 最多返回多少篇论文（默认 10）

        Returns:
            归一化后的候选论文列表（PaperCandidate）

        Raises:
            RuntimeError: 当 MCP adapter 调用失败时（例如超时、网络错误）
            Exception: 其他未捕获的异常会向上传播，由 runner 标记为 degraded
        """
        if self.client is None:
            raise RuntimeError("ArxivMCPAdapter client is not initialized")

        # 调用 MCP adapter 搜索论文
        # 异常会向上传播，由 runner 处理为 source-level failure
        raw_papers = self.client.search_papers(query=query, max_results=max_results)

        # 归一化为 PaperCandidate
        candidates = []
        for raw_paper in raw_papers:
            candidate = normalize_arxiv_paper(raw_paper)
            candidates.append(candidate)

        return candidates
