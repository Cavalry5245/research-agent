"""Tests for /api/conversations endpoints."""

import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.routers.conversations import set_memory_store
from app.services.memory_store import MemoryStore


@pytest.fixture(autouse=True)
def memory_store(tmp_path):
    db_path = tmp_path / "test_memory.db"
    store = MemoryStore(db_path)
    set_memory_store(store)
    yield store
    store.close()
    set_memory_store(None)


@pytest.fixture
def client():
    return TestClient(app)


def test_list_conversations_empty(client):
    resp = client.get("/api/conversations")
    assert resp.status_code == 200
    data = resp.json()
    assert data["conversations"] == []
    assert data["total"] == 0


def test_create_and_get_conversation(client, memory_store):
    cid = memory_store.create_conversation("Test conversation")
    memory_store.add_message(cid, "user", "Hello")
    memory_store.add_message(cid, "assistant", "Hi there")

    resp = client.get(f"/api/conversations/{cid}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["conversation"]["id"] == cid
    assert data["conversation"]["title"] == "Test conversation"
    assert len(data["messages"]) == 2
    assert data["messages"][0]["role"] == "user"
    assert data["messages"][1]["role"] == "assistant"


def test_list_conversations_returns_items(client, memory_store):
    memory_store.create_conversation("Conv 1")
    memory_store.create_conversation("Conv 2")

    resp = client.get("/api/conversations")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 2


def test_list_conversations_filters_by_metadata_kind(client, memory_store):
    qa_id = memory_store.create_conversation(
        "QA thread", metadata=json.dumps({"kind": "qa_thread"})
    )
    memory_store.create_conversation(
        "Regular chat", metadata=json.dumps({"kind": "chat"})
    )
    memory_store.create_conversation("No kind")

    resp = client.get("/api/conversations?kind=qa_thread")

    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 1
    assert data["conversations"][0]["id"] == qa_id
    assert data["conversations"][0]["metadata"] == {"kind": "qa_thread"}


def test_list_conversations_filters_by_metadata_kind_respects_offset(
    client, memory_store
):
    qa_ids = [
        memory_store.create_conversation(
            f"QA thread {i}", metadata=json.dumps({"kind": "qa_thread"})
        )
        for i in range(5)
    ]
    memory_store.create_conversation(
        "Regular chat", metadata=json.dumps({"kind": "chat"})
    )
    expected_ids = [
        c["id"]
        for c in memory_store.list_conversations(limit=20)
        if json.loads(c["metadata"]).get("kind") == "qa_thread"
    ][2:4]

    resp = client.get("/api/conversations?kind=qa_thread&limit=2&offset=2")

    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 2
    assert [c["id"] for c in data["conversations"]] == expected_ids
    assert set(expected_ids).issubset(set(qa_ids))


def test_conversation_detail_returns_message_metadata(client, memory_store):
    cid = memory_store.create_conversation(
        "QA thread", metadata=json.dumps({"kind": "qa_thread"})
    )
    memory_store.add_message(
        cid,
        "assistant",
        "Checked the failing test.",
        metadata=json.dumps({"source": "qa", "status": "done"}),
    )

    resp = client.get(f"/api/conversations/{cid}")

    assert resp.status_code == 200
    data = resp.json()
    assert data["conversation"]["metadata"] == {"kind": "qa_thread"}
    assert data["messages"][0]["metadata"] == {"source": "qa", "status": "done"}


def test_memory_store_updates_conversation_metadata(memory_store):
    cid = memory_store.create_conversation(
        "QA thread", metadata=json.dumps({"kind": "qa_thread", "status": "open"})
    )
    before = memory_store.get_conversation(cid)["updated_at"]

    memory_store.update_conversation_metadata(cid, {"status": "closed", "owner": "qa"})

    conv = memory_store.get_conversation(cid)
    assert json.loads(conv["metadata"]) == {
        "kind": "qa_thread",
        "status": "closed",
        "owner": "qa",
    }
    assert conv["updated_at"] >= before


def test_memory_store_updates_conversation_metadata_accepts_json_string(memory_store):
    cid = memory_store.create_conversation(
        "QA thread", metadata=json.dumps({"kind": "qa_thread", "status": "open"})
    )
    before = memory_store.get_conversation(cid)["updated_at"]

    memory_store.update_conversation_metadata(
        cid, json.dumps({"status": "closed", "owner": "qa"})
    )

    conv = memory_store.get_conversation(cid)
    assert json.loads(conv["metadata"]) == {
        "kind": "qa_thread",
        "status": "closed",
        "owner": "qa",
    }
    assert conv["updated_at"] >= before


def test_memory_store_updates_conversation_title(memory_store):
    cid = memory_store.create_conversation("Draft title")
    before = memory_store.get_conversation(cid)["updated_at"]

    memory_store.update_conversation_title(cid, "Final title")

    conv = memory_store.get_conversation(cid)
    assert conv["title"] == "Final title"
    assert conv["updated_at"] >= before


def test_delete_conversation(client, memory_store):
    cid = memory_store.create_conversation("To delete")

    resp = client.delete(f"/api/conversations/{cid}")
    assert resp.status_code == 200
    assert resp.json()["deleted"] is True

    resp = client.get(f"/api/conversations/{cid}")
    assert resp.status_code == 404


def test_get_nonexistent_conversation(client):
    resp = client.get("/api/conversations/nonexistent-id")
    assert resp.status_code == 404


def test_delete_nonexistent_conversation(client):
    resp = client.delete("/api/conversations/nonexistent-id")
    assert resp.status_code == 404
