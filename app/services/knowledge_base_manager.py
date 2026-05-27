from __future__ import annotations

import json
import logging
from pathlib import Path
from threading import Lock

from app.services.job_store import utc_now_iso

logger = logging.getLogger(__name__)

DEFAULT_KB_REGISTRY_PATH = Path("app/storage/metadata/knowledge_bases.json")
DEFAULT_KB = "default"


class KnowledgeBaseManager:
    def __init__(self, registry_path: str | Path = DEFAULT_KB_REGISTRY_PATH):
        self._path = Path(registry_path)
        self._lock = Lock()
        self._path.parent.mkdir(parents=True, exist_ok=True)

    def _load(self) -> dict:
        if not self._path.exists():
            return {
                "knowledge_bases": {
                    DEFAULT_KB: {
                        "id": DEFAULT_KB,
                        "name": "默认知识库",
                        "description": "",
                        "paper_ids": [],
                        "created_at": utc_now_iso(),
                    }
                }
            }
        try:
            return json.loads(self._path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return {"knowledge_bases": {}}

    def _save(self, data: dict) -> None:
        self._path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    def create_kb(self, kb_id: str, name: str, description: str = "") -> dict:
        with self._lock:
            data = self._load()
            kbs = data.setdefault("knowledge_bases", {})
            if kb_id in kbs:
                raise ValueError(f"Knowledge base '{kb_id}' already exists")
            entry = {
                "id": kb_id,
                "name": name,
                "description": description,
                "paper_ids": [],
                "created_at": utc_now_iso(),
            }
            kbs[kb_id] = entry
            self._save(data)
            return entry

    def get_kb(self, kb_id: str) -> dict | None:
        return self._load().get("knowledge_bases", {}).get(kb_id)

    def list_kbs(self) -> list[dict]:
        return list(self._load().get("knowledge_bases", {}).values())

    def add_paper_to_kb(self, kb_id: str, paper_id: str) -> dict:
        with self._lock:
            data = self._load()
            kb = data.get("knowledge_bases", {}).get(kb_id)
            if kb is None:
                raise ValueError(f"Knowledge base '{kb_id}' not found")
            if paper_id not in kb["paper_ids"]:
                kb["paper_ids"].append(paper_id)
                self._save(data)
            return kb

    def remove_paper_from_kb(self, kb_id: str, paper_id: str) -> dict:
        with self._lock:
            data = self._load()
            kb = data.get("knowledge_bases", {}).get(kb_id)
            if kb is None:
                raise ValueError(f"Knowledge base '{kb_id}' not found")
            kb["paper_ids"] = [pid for pid in kb["paper_ids"] if pid != paper_id]
            self._save(data)
            return kb

    def stats(self, kb_id: str) -> dict:
        kb = self.get_kb(kb_id)
        if kb is None:
            raise ValueError(f"Knowledge base '{kb_id}' not found")
        return {
            "id": kb["id"],
            "name": kb["name"],
            "paper_count": len(kb["paper_ids"]),
            "created_at": kb["created_at"],
        }
