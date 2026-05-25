"""Conversation history API endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.services.memory_store import MemoryStore

router = APIRouter(prefix="/api/conversations", tags=["conversations"])

_store_instance: MemoryStore | None = None


def get_memory_store() -> MemoryStore:
    global _store_instance
    if _store_instance is None:
        _store_instance = MemoryStore()
    return _store_instance


def set_memory_store(store: MemoryStore) -> None:
    global _store_instance
    _store_instance = store


class ConversationOut(BaseModel):
    id: str
    title: str
    created_at: float
    updated_at: float


class MessageOut(BaseModel):
    id: str
    role: str
    content: str
    created_at: float


class ConversationDetail(BaseModel):
    conversation: ConversationOut
    messages: list[MessageOut]


class ConversationListResponse(BaseModel):
    conversations: list[ConversationOut]
    total: int


@router.get("", response_model=ConversationListResponse)
def list_conversations(limit: int = 50, offset: int = 0):
    store = get_memory_store()
    convs = store.list_conversations(limit=limit, offset=offset)
    return ConversationListResponse(
        conversations=[
            ConversationOut(id=c["id"], title=c["title"], created_at=c["created_at"], updated_at=c["updated_at"])
            for c in convs
        ],
        total=len(convs),
    )


@router.get("/{conversation_id}", response_model=ConversationDetail)
def get_conversation(conversation_id: str):
    store = get_memory_store()
    conv = store.get_conversation(conversation_id)
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")
    messages = store.get_messages(conversation_id)
    return ConversationDetail(
        conversation=ConversationOut(
            id=conv["id"], title=conv["title"], created_at=conv["created_at"], updated_at=conv["updated_at"]
        ),
        messages=[
            MessageOut(id=m["id"], role=m["role"], content=m["content"], created_at=m["created_at"])
            for m in messages
        ],
    )


@router.delete("/{conversation_id}")
def delete_conversation(conversation_id: str):
    store = get_memory_store()
    deleted = store.delete_conversation(conversation_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return {"deleted": True, "conversation_id": conversation_id}
