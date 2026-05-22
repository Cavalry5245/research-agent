import os
import sys
import tempfile
from pathlib import Path

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.services.knowledge_base_manager import KnowledgeBaseManager


def _store():
    tmp = tempfile.TemporaryDirectory()
    mgr = KnowledgeBaseManager(Path(tmp.name) / "kbs.json")
    return mgr, tmp


def test_default_kb_is_created_on_first_load():
    mgr, tmp = _store()
    kbs = mgr.list_kbs()
    assert any(kb["id"] == "default" for kb in kbs)
    tmp.cleanup()


def test_create_kb_persists_metadata():
    mgr, tmp = _store()
    kb = mgr.create_kb("ml_basics", "ML 基础", "经典机器学习")
    assert kb["id"] == "ml_basics"
    assert kb["paper_ids"] == []

    fetched = mgr.get_kb("ml_basics")
    assert fetched["name"] == "ML 基础"
    tmp.cleanup()


def test_create_kb_rejects_duplicate():
    mgr, tmp = _store()
    mgr.create_kb("kb1", "n")
    with pytest.raises(ValueError):
        mgr.create_kb("kb1", "n2")
    tmp.cleanup()


def test_add_and_remove_papers():
    mgr, tmp = _store()
    mgr.create_kb("k", "n")
    mgr.add_paper_to_kb("k", "paper_001")
    mgr.add_paper_to_kb("k", "paper_002")
    mgr.add_paper_to_kb("k", "paper_001")

    kb = mgr.get_kb("k")
    assert kb["paper_ids"] == ["paper_001", "paper_002"]

    mgr.remove_paper_from_kb("k", "paper_001")
    assert mgr.get_kb("k")["paper_ids"] == ["paper_002"]
    tmp.cleanup()


def test_add_paper_to_missing_kb_raises():
    mgr, tmp = _store()
    with pytest.raises(ValueError):
        mgr.add_paper_to_kb("nope", "p1")
    tmp.cleanup()


def test_isolation_between_kbs():
    mgr, tmp = _store()
    mgr.create_kb("a", "A")
    mgr.create_kb("b", "B")
    mgr.add_paper_to_kb("a", "p1")
    mgr.add_paper_to_kb("b", "p2")
    assert mgr.get_kb("a")["paper_ids"] == ["p1"]
    assert mgr.get_kb("b")["paper_ids"] == ["p2"]
    tmp.cleanup()


def test_stats_reports_paper_count():
    mgr, tmp = _store()
    mgr.create_kb("k", "n")
    mgr.add_paper_to_kb("k", "p1")
    mgr.add_paper_to_kb("k", "p2")
    s = mgr.stats("k")
    assert s["paper_count"] == 2
    assert s["id"] == "k"
    tmp.cleanup()
