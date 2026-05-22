from __future__ import annotations

import json
import logging
from pathlib import Path
from threading import Lock
from typing import Any

from app.services.job_store import utc_now_iso

logger = logging.getLogger(__name__)

DEFAULT_VERSION_PATH = Path("app/storage/metadata/index_versions.json")


class IndexVersionStore:
    def __init__(self, path: str | Path = DEFAULT_VERSION_PATH):
        self._path = Path(path)
        self._lock = Lock()
        self._path.parent.mkdir(parents=True, exist_ok=True)

    def _load(self) -> dict[str, list[dict]]:
        if not self._path.exists():
            return {}
        try:
            return json.loads(self._path.read_text(encoding="utf-8") or "{}")
        except json.JSONDecodeError:
            return {}

    def _save(self, data: dict) -> None:
        self._path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    def record_version(
        self,
        paper_id: str,
        chunk_count: int,
        embedding_model: str,
        extra: dict[str, Any] | None = None,
    ) -> dict:
        with self._lock:
            data = self._load()
            versions = data.setdefault(paper_id, [])
            next_version = (max((v["version"] for v in versions), default=0) + 1)
            entry = {
                "paper_id": paper_id,
                "version": next_version,
                "created_at": utc_now_iso(),
                "chunk_count": chunk_count,
                "embedding_model": embedding_model,
            }
            if extra:
                entry.update(extra)
            versions.append(entry)
            self._save(data)
            return entry

    def list_versions(self, paper_id: str) -> list[dict]:
        return list(self._load().get(paper_id, []))

    def latest(self, paper_id: str) -> dict | None:
        versions = self.list_versions(paper_id)
        return versions[-1] if versions else None

    def rollback_to(self, paper_id: str, version: int) -> dict | None:
        with self._lock:
            data = self._load()
            versions = data.get(paper_id, [])
            target = next((v for v in versions if v["version"] == version), None)
            if target is None:
                return None
            data[paper_id] = [v for v in versions if v["version"] <= version]
            self._save(data)
            return target
