import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app import main as main_module
from app.main import app
from app.services.knowledge_base_manager import KnowledgeBaseManager


def _fresh_manager_client():
    tmp = tempfile.TemporaryDirectory()
    main_module._kb_manager = KnowledgeBaseManager(Path(tmp.name) / "kbs.json")
    return TestClient(app), tmp


def test_list_kbs_includes_default():
    client, tmp = _fresh_manager_client()
    resp = client.get("/kb")
    assert resp.status_code == 200
    body = resp.json()
    assert body["count"] >= 1
    ids = [kb["id"] for kb in body["knowledge_bases"]]
    assert "default" in ids
    tmp.cleanup()


def test_create_kb_returns_201_and_persists():
    client, tmp = _fresh_manager_client()
    resp = client.post(
        "/kb", json={"kb_id": "robotics", "name": "机器人", "description": "机器人相关"}
    )
    assert resp.status_code == 201
    assert resp.json()["id"] == "robotics"

    listed = client.get("/kb").json()
    assert any(kb["id"] == "robotics" for kb in listed["knowledge_bases"])
    tmp.cleanup()


def test_create_kb_duplicate_returns_409():
    client, tmp = _fresh_manager_client()
    client.post("/kb", json={"kb_id": "k1", "name": "n"})
    resp = client.post("/kb", json={"kb_id": "k1", "name": "n2"})
    assert resp.status_code == 409
    tmp.cleanup()


def test_create_kb_without_id_generates_id():
    client, tmp = _fresh_manager_client()
    resp = client.post("/kb", json={"name": "Graph RAG", "description": "retrieval"})

    assert resp.status_code == 201
    payload = resp.json()
    assert payload["id"] == "graph-rag"
    assert payload["name"] == "Graph RAG"
    assert payload["description"] == "retrieval"
    assert payload["updated_at"]
    tmp.cleanup()


def test_add_and_remove_paper_in_kb():
    client, tmp = _fresh_manager_client()
    client.post("/kb", json={"kb_id": "k", "name": "n"})

    add_resp = client.post("/kb/k/papers", json={"paper_id": "paper_001"})
    assert add_resp.status_code == 200
    assert add_resp.json()["paper_ids"] == ["paper_001"]

    rm_resp = client.delete("/kb/k/papers/paper_001")
    assert rm_resp.status_code == 200
    assert rm_resp.json()["paper_ids"] == []
    tmp.cleanup()


def test_kb_response_includes_derived_stats():
    client, tmp = _fresh_manager_client()
    note_dir = Path(tmp.name) / "notes"
    note_dir.mkdir()
    (note_dir / "paper_001_note.md").write_text("note", encoding="utf-8")

    class FakeVectorStore:
        def list_chunks(self, paper_id=None):
            chunks = [
                {
                    "paper_id": "paper_001",
                    "section": "Abstract",
                    "chunk_id": "paper_001_0",
                }
            ]
            if paper_id is None:
                return chunks
            return [chunk for chunk in chunks if chunk["paper_id"] == paper_id]

    main_module._vector_store = FakeVectorStore()

    with patch.object(main_module.settings, "note_dir", str(note_dir)):
        client.post("/kb", json={"kb_id": "k", "name": "n"})
        client.post("/kb/k/papers", json={"paper_id": "paper_001"})
        client.post("/kb/k/papers", json={"paper_id": "paper_002"})

        listed = client.get("/kb").json()

    payload = next(kb for kb in listed["knowledge_bases"] if kb["id"] == "k")
    assert payload["paper_count"] == 2
    assert payload["indexed_count"] == 1
    assert payload["noted_count"] == 1
    tmp.cleanup()


def test_add_paper_to_missing_kb_returns_404():
    client, tmp = _fresh_manager_client()
    resp = client.post("/kb/nope/papers", json={"paper_id": "p"})
    assert resp.status_code == 404
    tmp.cleanup()
