import json
import logging
import os
import threading
from collections import defaultdict
from typing import TYPE_CHECKING

from app.config import settings

if TYPE_CHECKING:
    from app.schemas import ParentDocument

logger = logging.getLogger(__name__)


class ParentDocumentStore:
    """
    父文档存储服务，基于 JSON 文件持久化。

    存储位置: app/storage/parent_docs/
    文件命名: {paper_id}_parents.json
    """

    def __init__(self, persist_dir: str | None = None):
        """
        初始化父文档存储。

        Args:
            persist_dir: 持久化目录，默认从 settings 读取
        """
        self.persist_dir = persist_dir or getattr(
            settings, "parent_doc_dir", "app/storage/parent_docs"
        )
        os.makedirs(self.persist_dir, exist_ok=True)

        # 内存索引: parent_id -> paper_id
        self._index: dict[str, str] = {}

        # 线程锁保护写操作
        self._lock = threading.RLock()

        # 初始化时构建索引
        self._build_index()

    def _build_index(self) -> None:
        """扫描所有 JSON 文件构建 parent_id -> paper_id 映射"""
        paper_count = 0
        parent_count = 0

        for filename in os.listdir(self.persist_dir):
            if not filename.endswith("_parents.json"):
                continue

            paper_id = filename.replace("_parents.json", "")
            file_path = os.path.join(self.persist_dir, filename)

            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    data = json.load(f)

                parents = data.get("parents", [])
                for parent in parents:
                    parent_id = parent.get("parent_id")
                    if parent_id:
                        self._index[parent_id] = paper_id
                        parent_count += 1

                paper_count += 1

            except (OSError, json.JSONDecodeError) as e:
                logger.warning(
                    "Failed to load parent documents from %s: %s", file_path, e
                )
                continue

        logger.info(
            "Loaded parent document index: %d papers, %d parents",
            paper_count,
            parent_count,
        )

    def _get_paper_file_path(self, paper_id: str) -> str:
        """获取论文父文档的文件路径"""
        return os.path.join(self.persist_dir, f"{paper_id}_parents.json")

    def _load_paper_file(self, paper_id: str) -> dict | None:
        """加载论文的父文档文件"""
        file_path = self._get_paper_file_path(paper_id)

        if not os.path.isfile(file_path):
            return None

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except (OSError, json.JSONDecodeError) as e:
            logger.warning("Failed to load %s: %s", file_path, e)
            return None

    def _save_paper_file(self, paper_id: str, data: dict) -> None:
        """保存论文的父文档文件"""
        file_path = self._get_paper_file_path(paper_id)

        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def add_parents(self, paper_id: str, parents: "list[ParentDocument]") -> int:
        """
        添加或更新论文的父文档。

        Args:
            paper_id: 论文 ID
            parents: 父文档列表

        Returns:
            添加的父文档数量

        Raises:
            ValueError: 如果 paper_id 为空或 parents 中的 paper_id 不匹配
        """
        if not paper_id:
            raise ValueError("paper_id cannot be empty")

        if not parents:
            return 0

        # 验证所有父文档的 paper_id 一致
        for parent in parents:
            if parent.paper_id != paper_id:
                raise ValueError(
                    f"Parent document {parent.parent_id} has mismatched paper_id: "
                    f"expected {paper_id}, got {parent.paper_id}"
                )

        with self._lock:
            # 准备数据
            data = {
                "paper_id": paper_id,
                "parents": [parent.model_dump() for parent in parents],
            }

            # 保存文件
            self._save_paper_file(paper_id, data)

            # 更新内存索引
            for parent in parents:
                self._index[parent.parent_id] = paper_id

            logger.info("Added %d parent documents for paper %s", len(parents), paper_id)
            return len(parents)

    def get_parent(self, parent_id: str) -> "ParentDocument | None":
        """
        获取单个父文档。

        Args:
            parent_id: 父文档 ID

        Returns:
            父文档对象，如果不存在返回 None
        """
        # 通过索引定位 paper_id
        paper_id = self._index.get(parent_id)
        if not paper_id:
            return None

        # 加载文件
        data = self._load_paper_file(paper_id)
        if not data:
            return None

        # 查找目标父文档
        from app.schemas import ParentDocument

        for parent_dict in data.get("parents", []):
            if parent_dict.get("parent_id") == parent_id:
                try:
                    return ParentDocument(**parent_dict)
                except (TypeError, ValueError) as e:
                    logger.warning(
                        "Invalid parent document %s in paper %s: %s",
                        parent_id,
                        paper_id,
                        e,
                    )
                    return None

        return None

    def get_parents(self, parent_ids: list[str]) -> "list[ParentDocument]":
        """
        批量获取父文档。

        Args:
            parent_ids: 父文档 ID 列表

        Returns:
            父文档列表（过滤掉不存在的 ID）
        """
        if not parent_ids:
            return []

        from app.schemas import ParentDocument

        # 按 paper_id 分组，减少文件 I/O
        papers_needed: dict[str, list[str]] = defaultdict(list)
        for pid in parent_ids:
            paper_id = self._index.get(pid)
            if paper_id:
                papers_needed[paper_id].append(pid)

        # 批量加载
        results: list[ParentDocument] = []
        for paper_id, pids_in_paper in papers_needed.items():
            data = self._load_paper_file(paper_id)
            if not data:
                continue

            pids_set = set(pids_in_paper)
            for parent_dict in data.get("parents", []):
                if parent_dict.get("parent_id") in pids_set:
                    try:
                        results.append(ParentDocument(**parent_dict))
                    except (TypeError, ValueError) as e:
                        logger.warning(
                            "Invalid parent document in paper %s: %s", paper_id, e
                        )

        return results

    def get_paper_parents(self, paper_id: str) -> "list[ParentDocument]":
        """
        获取论文的所有父文档。

        Args:
            paper_id: 论文 ID

        Returns:
            父文档列表，如果论文不存在返回空列表
        """
        from app.schemas import ParentDocument

        data = self._load_paper_file(paper_id)
        if not data:
            return []

        results: list[ParentDocument] = []
        for parent_dict in data.get("parents", []):
            try:
                results.append(ParentDocument(**parent_dict))
            except (TypeError, ValueError) as e:
                logger.warning("Invalid parent document in paper %s: %s", paper_id, e)

        return results

    def delete_paper(self, paper_id: str) -> int:
        """
        删除论文的所有父文档。

        Args:
            paper_id: 论文 ID

        Returns:
            删除的父文档数量
        """
        with self._lock:
            # 加载文件获取父文档数量
            data = self._load_paper_file(paper_id)
            if not data:
                return 0

            parent_count = len(data.get("parents", []))

            # 删除文件
            file_path = self._get_paper_file_path(paper_id)
            try:
                os.remove(file_path)
            except OSError as e:
                logger.warning("Failed to delete %s: %s", file_path, e)
                return 0

            # 更新内存索引
            parent_ids_to_remove = [
                pid for pid, pid_paper_id in self._index.items()
                if pid_paper_id == paper_id
            ]
            for pid in parent_ids_to_remove:
                del self._index[pid]

            logger.info("Deleted %d parent documents for paper %s", parent_count, paper_id)
            return parent_count

    def metadata(self) -> dict:
        """
        获取存储元数据。

        Returns:
            包含统计信息的字典：
            {
                "total_papers": int,
                "total_parents": int,
                "persist_dir": str
            }
        """
        # 统计论文数量
        paper_ids = set(self._index.values())
        total_papers = len(paper_ids)

        # 统计父文档数量
        total_parents = len(self._index)

        return {
            "total_papers": total_papers,
            "total_parents": total_parents,
            "persist_dir": self.persist_dir,
        }
