"""Tests for /api/conversations endpoints."""

import sys
import os
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from fastapi.testclient import TestClient

from app.services.memory_store import MemoryStore
from app.routers.conversations import set_memory_store
from app.main import app


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
