from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from threading import Lock

from app.services.job_store import utc_now_iso

logger = logging.getLogger(__name__)

DEFAULT_KB_REGISTRY_PATH = Path("app/storage/metadata/knowledge_bases.json")
DEFAULT_KB = "default"


def _slugify_name(name: str) -> str:
    value = re.sub(r"[^a-zA-Z0-9\u4e00-\u9fff]+", "-", name.strip().lower()).strip("-")
    return value or "research-set"


def _normalize_entry(entry: dict) -> dict:
    now = utc_now_iso()
    entry.setdefault("description", "")
    entry.setdefault("paper_ids", [])
    entry.setdefault("created_at", now)
    entry.setdefault("updated_at", entry.get("created_at") or now)
    return entry


class KnowledgeBaseManager:
    def __init__(self, registry_path: str | Path = DEFAULT_KB_REGISTRY_PATH):
        self._path = Path(registry_path)
        self._lock = Lock()
        self._path.parent.mkdir(parents=True, exist_ok=True)

    def _load(self) -> dict:
        if not self._path.exists():
            return {
                "knowledge_bases": {
                    DEFAULT_KB: _normalize_entry(
                        {
                            "id": DEFAULT_KB,
                            "name": "Default Research Set",
                            "description": "Papers not yet organized into a focused research set.",
                            "paper_ids": [],
                            "created_at": utc_now_iso(),
                        }
                    )
                }
            }
        try:
            data = json.loads(self._path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            data = {"knowledge_bases": {}}
        kbs = data.setdefault("knowledge_bases", {})
        for entry in kbs.values():
            _normalize_entry(entry)
        return data

    def _save(self, data: dict) -> None:
        self._path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    def _generate_kb_id_from_data(self, data: dict, name: str) -> str:
        existing = set(data.get("knowledge_bases", {}))
        base = _slugify_name(name)
        candidate = base
        suffix = 2
        while candidate in existing:
            candidate = f"{base}-{suffix}"
            suffix += 1
        return candidate

    def create_kb(self, kb_id: str | None, name: str, description: str = "") -> dict:
        with self._lock:
            data = self._load()
            kbs = data.setdefault("knowledge_bases", {})
            resolved_id = kb_id.strip() if kb_id else self._generate_kb_id_from_data(data, name)
            if resolved_id in kbs:
                raise ValueError(f"Knowledge base '{resolved_id}' already exists")
            now = utc_now_iso()
            entry = {
                "id": resolved_id,
                "name": name,
                "description": description,
                "paper_ids": [],
                "created_at": now,
                "updated_at": now,
            }
            kbs[resolved_id] = entry
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
                kb["updated_at"] = utc_now_iso()
                self._save(data)
            return kb

    def remove_paper_from_kb(self, kb_id: str, paper_id: str) -> dict:
        with self._lock:
            data = self._load()
            kb = data.get("knowledge_bases", {}).get(kb_id)
            if kb is None:
                raise ValueError(f"Knowledge base '{kb_id}' not found")
            before = list(kb["paper_ids"])
            kb["paper_ids"] = [pid for pid in before if pid != paper_id]
            if kb["paper_ids"] != before:
                kb["updated_at"] = utc_now_iso()
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
            "updated_at": kb["updated_at"],
        }
