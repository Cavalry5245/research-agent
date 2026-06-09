from __future__ import annotations

import json
import os
from pathlib import Path
from threading import Lock
from typing import Callable

from app.research_workflow.schemas import ResearchRun


_LOCK_REGISTRY_LOCK = Lock()
_PATH_LOCKS: dict[Path, Lock] = {}


def _get_path_lock(path: Path) -> Lock:
    with _LOCK_REGISTRY_LOCK:
        lock = _PATH_LOCKS.get(path)
        if lock is None:
            lock = Lock()
            _PATH_LOCKS[path] = lock
        return lock


class FileResearchRunStore:
    def __init__(self, path: str | Path) -> None:
        self._path = Path(path).expanduser().resolve(strict=False)
        self._lock = _get_path_lock(self._path)
        self._path.parent.mkdir(parents=True, exist_ok=True)

    def upsert(self, run: ResearchRun) -> ResearchRun:
        with self._lock:
            runs = self._load_unlocked()
            runs[run.run_id] = run
            self._save_unlocked(runs)
        return run

    def update(
        self,
        run_id: str,
        updater: Callable[[ResearchRun], ResearchRun],
    ) -> ResearchRun | None:
        with self._lock:
            runs = self._load_unlocked()
            run = runs.get(run_id)
            if run is None:
                return None
            updated = updater(run)
            runs[updated.run_id] = updated
            if updated.run_id != run_id:
                runs.pop(run_id, None)
            self._save_unlocked(runs)
        return updated

    def get(self, run_id: str) -> ResearchRun | None:
        with self._lock:
            return self._load_unlocked().get(run_id)

    def list(self) -> list[ResearchRun]:
        with self._lock:
            runs = self._load_unlocked()
            return sorted(runs.values(), key=lambda run: run.created_at, reverse=True)

    def clear(self) -> None:
        with self._lock:
            self._save_unlocked({})

    def _load_unlocked(self) -> dict[str, ResearchRun]:
        if not self._path.exists():
            return {}

        raw = self._path.read_text(encoding="utf-8").strip()
        if not raw:
            return {}

        payload = json.loads(raw)
        runs: dict[str, ResearchRun] = {}
        for item in payload.get("runs", []):
            run = ResearchRun.model_validate(item)
            runs[run.run_id] = run
        return runs

    def _save_unlocked(self, runs: dict[str, ResearchRun]) -> None:
        payload = {
            "runs": [run.model_dump(mode="json") for run in runs.values()],
        }
        temp_path = self._path.with_name(f".{self._path.name}.tmp")
        temp_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        os.replace(temp_path, self._path)
