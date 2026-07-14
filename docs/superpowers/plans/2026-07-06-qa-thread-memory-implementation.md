# QA Thread Memory Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build Codex-like QA thread memory for ResearchAgent so QA conversations persist on the backend, support follow-up question rewriting, restore recent threads in the React QA page, and keep answers grounded in current RAG sources.

**Architecture:** Add a focused backend `QAMemoryService` between `POST /qa` and `answer_question()`. Reuse the existing SQLite-backed `MemoryStore` for thread persistence, extend conversation APIs to expose/filter metadata, add prompt builders for rewrite/summary/answer context, then update the React QA page to use server-backed conversations instead of local-only storage.

**Tech Stack:** FastAPI, Pydantic, SQLite via `MemoryStore`, existing `LLMClient`, existing RAG `answer_question()`, React 18, TanStack Query, Vitest, pytest.

---

## Current Branch And Guardrails

- Work on branch: `codex/qa-thread-memory`.
- There is an unrelated dirty file in the checkout: `.claude/settings.json`. Do not edit, stage, or commit it.
- Do not use recursive deletion commands. If test temp directories need cleanup, leave them or delete one explicit file/path at a time.
- Use the project Python interpreter for backend tests:

```powershell
& 'D:\Hcworkspace\Anoconda3\envs\research_agent\python.exe' -m pytest <tests> -q --basetemp .pytest-tmp-qa-thread-memory
```

## File Structure

Create:

- `app/services/qa_memory.py`
  Owns QA thread lifecycle, metadata parsing/serialization, recent-turn assembly, query rewrite, summary update, and persistence of QA user/assistant messages.

- `tests/test_qa_memory.py`
  Unit tests for `QAMemoryService` without FastAPI.

- `tests/test_qa_thread_api.py`
  API-level tests for `POST /qa`, conversation metadata filtering, metadata restoration, deletion behavior, and error paths.

- `frontend/src/api/conversations.ts`
  React API client for listing, loading, and deleting conversations.

Modify:

- `app/services/memory_store.py`
  Add update/list helpers needed by conversation metadata filtering.

- `app/routers/conversations.py`
  Expose `metadata` on conversation/message responses and support `kind=qa` filtering.

- `app/prompts/qa_prompt.py`
  Add query rewrite, contextual QA, and summary update prompt builders while preserving existing `build_qa_prompt(question, context)` compatibility.

- `app/schemas.py`
  Extend `QARequest` and `QAResponse` with `conversation_id` and `rewritten_question`.

- `app/main.py`
  Route `/qa` through `QAMemoryService`; keep existing retriever/reranker wiring.

- `tests/test_api_conversations.py`
  Add metadata exposure and kind filtering coverage.

- `tests/test_paper_qa.py`
  Update prompt assertions for the expanded QA prompt while preserving the evidence-grounding contract.

- `frontend/src/api/qa.ts`
  Add `conversation_id` to request/response flow.

- `frontend/src/api/types.ts`
  Add conversation and QA thread metadata types.

- `frontend/src/pages/qa/QaPage.tsx`
  Replace local-only conversation state with backend-backed thread state, recent QA thread list, New chat, Clear conversation deletion, restored sources, and collapsible rewritten query.

- `frontend/src/pages/qa/QaPage.test.tsx`
  Replace localStorage-only tests with server-backed conversation tests.

---

### Task 1: Extend MemoryStore And Conversation API Metadata

**Files:**
- Modify: `app/services/memory_store.py`
- Modify: `app/routers/conversations.py`
- Modify: `tests/test_api_conversations.py`

- [ ] **Step 1: Add failing MemoryStore helper tests inside `tests/test_api_conversations.py`**

Append these tests to `tests/test_api_conversations.py`:

```python
import json


def test_list_conversations_filters_by_metadata_kind(client, memory_store):
    qa_id = memory_store.create_conversation(
        "QA thread", metadata=json.dumps({"kind": "qa"}, ensure_ascii=False)
    )
    memory_store.create_conversation(
        "Agent thread", metadata=json.dumps({"kind": "agent"}, ensure_ascii=False)
    )

    resp = client.get("/api/conversations?kind=qa")

    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 1
    assert data["conversations"][0]["id"] == qa_id
    assert data["conversations"][0]["metadata"]["kind"] == "qa"


def test_conversation_detail_returns_message_metadata(client, memory_store):
    cid = memory_store.create_conversation(
        "QA detail", metadata=json.dumps({"kind": "qa"}, ensure_ascii=False)
    )
    memory_store.add_message(
        cid,
        "assistant",
        "Answer",
        metadata=json.dumps(
            {"kind": "qa_assistant", "rewritten_question": "Standalone?"},
            ensure_ascii=False,
        ),
    )

    resp = client.get(f"/api/conversations/{cid}")

    assert resp.status_code == 200
    data = resp.json()
    assert data["conversation"]["metadata"]["kind"] == "qa"
    assert data["messages"][0]["metadata"]["kind"] == "qa_assistant"
    assert data["messages"][0]["metadata"]["rewritten_question"] == "Standalone?"


def test_memory_store_updates_conversation_metadata(memory_store):
    cid = memory_store.create_conversation(
        "QA thread", metadata=json.dumps({"kind": "qa"}, ensure_ascii=False)
    )

    updated = memory_store.update_conversation_metadata(
        cid,
        json.dumps({"kind": "qa", "summary": "Discusses Grounding DINO."}, ensure_ascii=False),
    )

    assert updated is True
    conv = memory_store.get_conversation(cid)
    assert json.loads(conv["metadata"])["summary"] == "Discusses Grounding DINO."
```

- [ ] **Step 2: Run the failing tests**

Run:

```powershell
& 'D:\Hcworkspace\Anoconda3\envs\research_agent\python.exe' -m pytest tests/test_api_conversations.py -q --basetemp .pytest-tmp-qa-thread-memory
```

Expected: FAIL because `ConversationOut` and `MessageOut` do not expose `metadata`, `kind` filtering does not exist, and `MemoryStore.update_conversation_metadata()` is missing.

- [ ] **Step 3: Add `MemoryStore.update_conversation_metadata()` and filtered listing**

In `app/services/memory_store.py`, add `json` import and these methods near the existing conversation methods:

```python
import json
```

```python
    def update_conversation_metadata(self, conv_id: str, metadata: str) -> bool:
        now = time.time()
        conn = self._get_conn()
        cursor = conn.execute(
            "UPDATE conversations SET metadata = ?, updated_at = ? WHERE id = ?",
            (metadata, now, conv_id),
        )
        conn.commit()
        return cursor.rowcount > 0

    def update_conversation_title(self, conv_id: str, title: str) -> bool:
        now = time.time()
        conn = self._get_conn()
        cursor = conn.execute(
            "UPDATE conversations SET title = ?, updated_at = ? WHERE id = ?",
            (title, now, conv_id),
        )
        conn.commit()
        return cursor.rowcount > 0

    def list_conversations_by_kind(
        self, kind: str, limit: int = 50, offset: int = 0
    ) -> list[dict]:
        conversations = self.list_conversations(limit=1000, offset=0)
        matched: list[dict] = []
        for conversation in conversations:
            try:
                metadata = json.loads(conversation.get("metadata") or "{}")
            except json.JSONDecodeError:
                metadata = {}
            if metadata.get("kind") == kind:
                matched.append(conversation)
        return matched[offset : offset + limit]
```

- [ ] **Step 4: Expose metadata and kind filtering in `app/routers/conversations.py`**

Replace the Pydantic response models and route mapping portions with:

```python
import json
from typing import Any
```

```python
def _decode_metadata(raw: str | None) -> dict[str, Any]:
    if not raw:
        return {}
    try:
        metadata = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    return metadata if isinstance(metadata, dict) else {}
```

```python
class ConversationOut(BaseModel):
    id: str
    title: str
    created_at: float
    updated_at: float
    metadata: dict[str, Any] = {}


class MessageOut(BaseModel):
    id: str
    role: str
    content: str
    created_at: float
    metadata: dict[str, Any] = {}
```

Update `list_conversations()`:

```python
@router.get("", response_model=ConversationListResponse)
def list_conversations(limit: int = 50, offset: int = 0, kind: str | None = None):
    store = get_memory_store()
    if kind:
        convs = store.list_conversations_by_kind(kind=kind, limit=limit, offset=offset)
    else:
        convs = store.list_conversations(limit=limit, offset=offset)
    return ConversationListResponse(
        conversations=[
            ConversationOut(
                id=c["id"],
                title=c["title"],
                created_at=c["created_at"],
                updated_at=c["updated_at"],
                metadata=_decode_metadata(c.get("metadata")),
            )
            for c in convs
        ],
        total=len(convs),
    )
```

Update `get_conversation()` mappings:

```python
        conversation=ConversationOut(
            id=conv["id"],
            title=conv["title"],
            created_at=conv["created_at"],
            updated_at=conv["updated_at"],
            metadata=_decode_metadata(conv.get("metadata")),
        ),
```

```python
            MessageOut(
                id=m["id"],
                role=m["role"],
                content=m["content"],
                created_at=m["created_at"],
                metadata=_decode_metadata(m.get("metadata")),
            )
```

- [ ] **Step 5: Run conversation API tests**

Run:

```powershell
& 'D:\Hcworkspace\Anoconda3\envs\research_agent\python.exe' -m pytest tests/test_api_conversations.py -q --basetemp .pytest-tmp-qa-thread-memory
```

Expected: PASS.

- [ ] **Step 6: Commit Task 1**

Run:

```powershell
git add app/services/memory_store.py app/routers/conversations.py tests/test_api_conversations.py
git commit -m "feat: expose conversation metadata"
```

Expected: commit succeeds and `.claude/settings.json` remains unstaged.

---

### Task 2: Add Prompt Builders For QA Thread Memory

**Files:**
- Modify: `app/prompts/qa_prompt.py`
- Modify: `tests/test_paper_qa.py`

- [ ] **Step 1: Add failing prompt tests**

Append these tests to `tests/test_paper_qa.py`:

```python
from app.prompts.qa_prompt import (
    build_contextual_qa_prompt,
    build_query_rewrite_prompt,
    build_summary_update_prompt,
)


def test_build_query_rewrite_prompt_contains_memory_boundaries():
    prompt = build_query_rewrite_prompt(
        question="它的 zero-shot 指标是多少？",
        conversation_summary="上一轮讨论 Grounding DINO 的核心方法。",
        recent_turns="User: Grounding DINO 的核心方法是什么？\nAssistant: 它结合 DINO 和 grounded pre-training。",
        paper_id="paper_001",
        previous_rewritten_question="Grounding DINO 的核心方法是什么？",
    )

    assert "它的 zero-shot 指标是多少？" in prompt
    assert "Grounding DINO" in prompt
    assert "不要回答问题" in prompt
    assert "只输出改写后的检索问题" in prompt


def test_build_contextual_qa_prompt_keeps_history_out_of_facts():
    prompt = build_contextual_qa_prompt(
        question="它的指标是多少？",
        rewritten_question="Grounding DINO 的 zero-shot 检测指标是多少？",
        context="[paper_001 p.2 Results]\n52.5 AP on COCO zero-shot.",
        conversation_summary="上一轮讨论 Grounding DINO。",
        recent_turns="User: 核心方法是什么？\nAssistant: 结合检测器和语言 grounding。",
    )

    assert "会话摘要" in prompt
    assert "最近对话" in prompt
    assert "本轮检索到的论文证据" in prompt
    assert "不能作为论文事实依据" in prompt
    assert "52.5 AP" in prompt


def test_build_summary_update_prompt_warns_against_fact_memory():
    prompt = build_summary_update_prompt(
        previous_summary="上一轮讨论 Grounding DINO。",
        recent_turns="User: 它的指标是多少？\nAssistant: 52.5 AP。",
        rewritten_question="Grounding DINO 的 zero-shot 检测指标是多少？",
        source_notes="paper_001 Results p.2",
    )

    assert "会话状态摘要" in prompt
    assert "不要把 assistant answer 改写成无来源的长期事实" in prompt
    assert "paper_001 Results p.2" in prompt
```

- [ ] **Step 2: Run prompt tests to verify failure**

Run:

```powershell
& 'D:\Hcworkspace\Anoconda3\envs\research_agent\python.exe' -m pytest tests/test_paper_qa.py::test_build_query_rewrite_prompt_contains_memory_boundaries tests/test_paper_qa.py::test_build_contextual_qa_prompt_keeps_history_out_of_facts tests/test_paper_qa.py::test_build_summary_update_prompt_warns_against_fact_memory -q --basetemp .pytest-tmp-qa-thread-memory
```

Expected: FAIL because the new prompt builders do not exist.

- [ ] **Step 3: Add prompt builders while preserving `build_qa_prompt()`**

Replace `app/prompts/qa_prompt.py` with:

```python
QA_PROMPT = """你是一个严谨的科研论文问答助手。请只根据给定上下文回答用户问题。
要求：
1. 不要使用上下文之外的知识编造答案。
2. 如果上下文不足，请明确说明“根据当前论文片段无法判断”。
3. 回答应结构清晰，适合科研人员阅读。
4. 涉及方法、实验、指标时要尽量具体。
5. 回答后列出依据片段编号。

用户问题：
{question}

检索到的论文片段：
{context}
"""


CONTEXTUAL_QA_PROMPT = """你是一个严谨的科研论文问答助手。请只根据本轮检索到的论文证据回答用户问题。

会话摘要：
{conversation_summary}

最近对话：
{recent_turns}

用户原始问题：
{question}

用于检索的改写问题：
{rewritten_question}

本轮检索到的论文证据：
{context}

要求：
1. 会话摘要和最近对话只用于理解指代和任务上下文，不能作为论文事实依据。
2. 答案必须来自本轮检索到的论文证据。
3. 如果证据不足，明确说明“根据当前论文片段无法判断”。
4. 如果历史和本轮证据冲突，以本轮证据为准。
5. 回答后列出依据片段编号或来源信息。
"""


QUERY_REWRITE_PROMPT = """你要把科研论文 QA 对话中的当前问题改写成独立、适合检索的查询。

会话摘要：
{conversation_summary}

最近对话：
{recent_turns}

当前论文范围：
{paper_id}

上一轮改写问题：
{previous_rewritten_question}

当前问题：
{question}

要求：
1. 只补全指代、省略和上下文对象。
2. 不要引入历史中没有出现的新事实。
3. 不要回答问题。
4. 如果当前问题已经独立，保持原意并轻微规范化。
5. 保持用户语言，中文问题输出中文。
6. 只输出改写后的检索问题，不要输出解释。
"""


SUMMARY_UPDATE_PROMPT = """你要更新科研 QA thread 的会话状态摘要。

旧会话状态摘要：
{previous_summary}

最近对话：
{recent_turns}

本轮改写问题：
{rewritten_question}

本轮来源提示：
{source_notes}

要求：
1. 输出一段简洁的会话状态摘要，说明当前讨论主题、被反复指代的对象、用户关注维度和后续追问需要的上下文。
2. 不要把 assistant answer 改写成无来源的长期事实。
3. 不要把无法由来源提示支持的内容写成确定结论。
4. 摘要只服务本会话后续追问，不替代论文检索。
"""


def build_qa_prompt(question: str, context: str) -> str:
    return QA_PROMPT.format(question=question, context=context)


def build_contextual_qa_prompt(
    question: str,
    rewritten_question: str,
    context: str,
    conversation_summary: str = "",
    recent_turns: str = "",
) -> str:
    return CONTEXTUAL_QA_PROMPT.format(
        question=question,
        rewritten_question=rewritten_question,
        context=context,
        conversation_summary=conversation_summary or "无",
        recent_turns=recent_turns or "无",
    )


def build_query_rewrite_prompt(
    question: str,
    conversation_summary: str = "",
    recent_turns: str = "",
    paper_id: str | None = None,
    previous_rewritten_question: str = "",
) -> str:
    return QUERY_REWRITE_PROMPT.format(
        question=question,
        conversation_summary=conversation_summary or "无",
        recent_turns=recent_turns or "无",
        paper_id=paper_id or "全库",
        previous_rewritten_question=previous_rewritten_question or "无",
    )


def build_summary_update_prompt(
    previous_summary: str = "",
    recent_turns: str = "",
    rewritten_question: str = "",
    source_notes: str = "",
) -> str:
    return SUMMARY_UPDATE_PROMPT.format(
        previous_summary=previous_summary or "无",
        recent_turns=recent_turns or "无",
        rewritten_question=rewritten_question or "无",
        source_notes=source_notes or "无",
    )
```

- [ ] **Step 4: Run prompt tests**

Run:

```powershell
& 'D:\Hcworkspace\Anoconda3\envs\research_agent\python.exe' -m pytest tests/test_paper_qa.py -q --basetemp .pytest-tmp-qa-thread-memory
```

Expected: PASS. Existing `build_qa_prompt()` tests continue passing.

- [ ] **Step 5: Commit Task 2**

Run:

```powershell
git add app/prompts/qa_prompt.py tests/test_paper_qa.py
git commit -m "feat: add QA memory prompts"
```

Expected: commit succeeds and unrelated `.claude/settings.json` remains unstaged.

---

### Task 3: Build `QAMemoryService`

**Files:**
- Create: `app/services/qa_memory.py`
- Create: `tests/test_qa_memory.py`

- [ ] **Step 1: Create failing service tests**

Create `tests/test_qa_memory.py`:

```python
import json
from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException

from app.services.memory_store import MemoryStore


def _make_service(store=None, llm=None, answer_fn=None):
    from app.services.qa_memory import QAMemoryService

    store = store or MemoryStore(":memory:")
    llm = llm or MagicMock()
    answer_fn = answer_fn or MagicMock(
        return_value={
            "question": "rewritten question",
            "answer": "grounded answer",
            "sources": [
                {
                    "paper_id": "paper_001",
                    "title": "Grounding DINO",
                    "section": "Results",
                    "chunk_id": "chunk_1",
                    "content": "52.5 AP on COCO zero-shot.",
                    "score": 0.9,
                }
            ],
            "retrieval_time": 0.1,
            "llm_time": 0.2,
        }
    )
    service = QAMemoryService(store=store, llm_client=llm)
    return service, store, llm, answer_fn


def test_ask_creates_qa_conversation_and_persists_messages():
    service, store, llm, answer_fn = _make_service()
    llm.generate_text.return_value = "Grounding DINO zero-shot metrics?"

    result = service.ask(
        question="它的 zero-shot 指标是多少？",
        paper_id="paper_001",
        top_k=5,
        answer_fn=answer_fn,
    )

    assert result["conversation_id"]
    assert result["rewritten_question"] == "Grounding DINO zero-shot metrics?"
    messages = store.get_messages(result["conversation_id"])
    assert [m["role"] for m in messages] == ["user", "assistant"]
    user_meta = json.loads(messages[0]["metadata"])
    assistant_meta = json.loads(messages[1]["metadata"])
    assert user_meta["kind"] == "qa_user"
    assert user_meta["paper_id"] == "paper_001"
    assert assistant_meta["kind"] == "qa_assistant"
    assert assistant_meta["rewritten_question"] == "Grounding DINO zero-shot metrics?"
    assert assistant_meta["sources"][0]["chunk_id"] == "chunk_1"
    answer_fn.assert_called_once()
    assert answer_fn.call_args.kwargs["question"] == "Grounding DINO zero-shot metrics?"


def test_ask_reuses_existing_qa_conversation_and_includes_recent_turns():
    service, store, llm, answer_fn = _make_service()
    cid = store.create_conversation(
        "Existing QA", metadata=json.dumps({"kind": "qa", "summary": "Discussing Grounding DINO."})
    )
    store.add_message(cid, "user", "Grounding DINO 的核心方法是什么？", metadata=json.dumps({"kind": "qa_user"}))
    store.add_message(
        cid,
        "assistant",
        "它结合 DINO 和 grounded pre-training。",
        metadata=json.dumps({"kind": "qa_assistant", "rewritten_question": "Grounding DINO 的核心方法是什么？"}),
    )
    llm.generate_text.return_value = "Grounding DINO 的 zero-shot 检测指标是多少？"

    result = service.ask(
        question="它的 zero-shot 指标是多少？",
        paper_id="paper_001",
        top_k=5,
        conversation_id=cid,
        answer_fn=answer_fn,
    )

    assert result["conversation_id"] == cid
    rewrite_prompt = llm.generate_text.call_args_list[0].args[0]
    assert "Discussing Grounding DINO." in rewrite_prompt
    assert "核心方法" in rewrite_prompt
    assert store.count_messages(cid) == 4


def test_ask_rejects_missing_conversation_id():
    service, _, _, answer_fn = _make_service()

    with pytest.raises(HTTPException) as exc:
        service.ask(
            question="Follow up?",
            conversation_id="missing",
            answer_fn=answer_fn,
        )

    assert exc.value.status_code == 404
    answer_fn.assert_not_called()


def test_ask_rejects_non_qa_conversation():
    service, store, _, answer_fn = _make_service()
    cid = store.create_conversation("Agent thread", metadata=json.dumps({"kind": "agent"}))

    with pytest.raises(HTTPException) as exc:
        service.ask(
            question="Follow up?",
            conversation_id=cid,
            answer_fn=answer_fn,
        )

    assert exc.value.status_code == 400
    answer_fn.assert_not_called()


def test_rewrite_failure_uses_original_question_and_records_metadata():
    service, store, llm, answer_fn = _make_service()
    llm.generate_text.side_effect = RuntimeError("rewrite unavailable")

    result = service.ask(
        question="它的指标是多少？",
        paper_id="paper_001",
        answer_fn=answer_fn,
    )

    assert result["rewritten_question"] == "它的指标是多少？"
    answer_fn.assert_called_once()
    assert answer_fn.call_args.kwargs["question"] == "它的指标是多少？"
    messages = store.get_messages(result["conversation_id"])
    assistant_meta = json.loads(messages[1]["metadata"])
    assert assistant_meta["rewrite_failed"] is True


def test_summary_update_runs_after_threshold_and_failure_does_not_block():
    service, store, llm, answer_fn = _make_service()
    cid = store.create_conversation("Long QA", metadata=json.dumps({"kind": "qa", "summary": ""}))
    for i in range(10):
        store.add_message(cid, "user", f"Question {i}", metadata=json.dumps({"kind": "qa_user"}))
    llm.generate_text.side_effect = ["rewritten question", RuntimeError("summary failed")]

    result = service.ask(
        question="Follow up?",
        conversation_id=cid,
        answer_fn=answer_fn,
    )

    assert result["conversation_id"] == cid
    conv = store.get_conversation(cid)
    metadata = json.loads(conv["metadata"])
    assert metadata["kind"] == "qa"
```

- [ ] **Step 2: Run service tests to verify failure**

Run:

```powershell
& 'D:\Hcworkspace\Anoconda3\envs\research_agent\python.exe' -m pytest tests/test_qa_memory.py -q --basetemp .pytest-tmp-qa-thread-memory
```

Expected: FAIL because `app.services.qa_memory` does not exist.

- [ ] **Step 3: Implement `app/services/qa_memory.py`**

Create `app/services/qa_memory.py`:

```python
from __future__ import annotations

import json
import logging
import time
from collections.abc import Callable
from typing import Any

from fastapi import HTTPException

from app.prompts.qa_prompt import (
    build_query_rewrite_prompt,
    build_summary_update_prompt,
)
from app.services.llm_client import LLMClient
from app.services.memory_store import MemoryStore

logger = logging.getLogger(__name__)

RECENT_MESSAGE_LIMIT = 8
SUMMARY_MESSAGE_THRESHOLD = 10
SUMMARY_MIN_NEW_MESSAGES = 4

AnswerFn = Callable[..., dict[str, Any]]


def _metadata(raw: str | None) -> dict[str, Any]:
    if not raw:
        return {}
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}


def _metadata_json(data: dict[str, Any]) -> str:
    return json.dumps(data, ensure_ascii=False)


def _title_from_question(question: str) -> str:
    compact = " ".join(question.split())
    return compact[:80] or "QA conversation"


class QAMemoryService:
    def __init__(
        self,
        store: MemoryStore | None = None,
        llm_client: LLMClient | None = None,
        recent_message_limit: int = RECENT_MESSAGE_LIMIT,
        summary_message_threshold: int = SUMMARY_MESSAGE_THRESHOLD,
        summary_min_new_messages: int = SUMMARY_MIN_NEW_MESSAGES,
    ):
        self.store = store or MemoryStore()
        self.llm_client = llm_client or LLMClient()
        self.recent_message_limit = recent_message_limit
        self.summary_message_threshold = summary_message_threshold
        self.summary_min_new_messages = summary_min_new_messages

    def ask(
        self,
        question: str,
        answer_fn: AnswerFn,
        paper_id: str | None = None,
        top_k: int = 5,
        conversation_id: str | None = None,
        **answer_kwargs: Any,
    ) -> dict[str, Any]:
        conversation_id = self._load_or_create_conversation(
            question=question,
            paper_id=paper_id,
            conversation_id=conversation_id,
        )
        conv = self.store.get_conversation(conversation_id)
        conv_meta = _metadata(conv.get("metadata") if conv else "{}")
        messages_before = self.store.get_messages(
            conversation_id, limit=self.recent_message_limit
        )
        recent_turns = self._format_recent_turns(messages_before)
        summary = str(conv_meta.get("summary") or "")
        previous_rewritten = str(conv_meta.get("last_rewritten_question") or "")

        rewritten_question = question
        rewrite_failed = False
        try:
            prompt = build_query_rewrite_prompt(
                question=question,
                conversation_summary=summary,
                recent_turns=recent_turns,
                paper_id=paper_id,
                previous_rewritten_question=previous_rewritten,
            )
            candidate = self.llm_client.generate_text(prompt).strip()
            if candidate:
                rewritten_question = candidate
        except Exception as exc:
            rewrite_failed = True
            logger.warning("QA query rewrite failed: %s", exc)

        self.store.add_message(
            conversation_id,
            "user",
            question,
            metadata=_metadata_json(
                {
                    "kind": "qa_user",
                    "paper_id": paper_id,
                    "top_k": top_k,
                }
            ),
        )

        try:
            result = answer_fn(
                question=rewritten_question,
                paper_id=paper_id,
                top_k=top_k,
                conversation_summary=summary,
                recent_turns=recent_turns,
                original_question=question,
                **answer_kwargs,
            )
        except Exception as exc:
            self.store.add_message(
                conversation_id,
                "assistant",
                str(exc),
                metadata=_metadata_json(
                    {
                        "kind": "qa_assistant",
                        "status": "error",
                        "error": str(exc),
                        "paper_id": paper_id,
                        "top_k": top_k,
                        "rewritten_question": rewritten_question,
                        "rewrite_failed": rewrite_failed,
                    }
                ),
            )
            raise

        assistant_meta = {
            "kind": "qa_assistant",
            "status": "done",
            "paper_id": paper_id,
            "top_k": top_k,
            "rewritten_question": rewritten_question,
            "sources": result.get("sources", []),
            "retrieval_time": result.get("retrieval_time"),
            "llm_time": result.get("llm_time"),
            "rewrite_failed": rewrite_failed,
        }
        self.store.add_message(
            conversation_id,
            "assistant",
            str(result.get("answer", "")),
            metadata=_metadata_json(assistant_meta),
        )

        self._update_conversation_metadata(
            conversation_id=conversation_id,
            paper_id=paper_id,
            last_rewritten_question=rewritten_question,
        )
        self._maybe_update_summary(conversation_id, rewritten_question, result.get("sources", []))

        return {
            "question": question,
            "rewritten_question": rewritten_question,
            "answer": result.get("answer", ""),
            "sources": result.get("sources", []),
            "conversation_id": conversation_id,
            "retrieval_time": result.get("retrieval_time"),
            "llm_time": result.get("llm_time"),
        }

    def _load_or_create_conversation(
        self,
        question: str,
        paper_id: str | None,
        conversation_id: str | None,
    ) -> str:
        if not conversation_id:
            metadata = {
                "kind": "qa",
                "summary": "",
                "summary_updated_at": None,
                "default_paper_id": paper_id,
                "last_rewritten_question": "",
                "summary_message_count": 0,
            }
            return self.store.create_conversation(
                title=_title_from_question(question),
                metadata=_metadata_json(metadata),
            )

        conversation = self.store.get_conversation(conversation_id)
        if not conversation:
            raise HTTPException(status_code=404, detail="Conversation not found")
        metadata = _metadata(conversation.get("metadata"))
        if metadata.get("kind") != "qa":
            raise HTTPException(status_code=400, detail="Conversation is not a QA thread")
        return conversation_id

    def _format_recent_turns(self, messages: list[dict]) -> str:
        if not messages:
            return ""
        lines: list[str] = []
        for message in messages[-self.recent_message_limit :]:
            role = str(message.get("role") or "user")
            content = " ".join(str(message.get("content") or "").split())
            metadata = _metadata(message.get("metadata"))
            rewritten = metadata.get("rewritten_question")
            if rewritten:
                lines.append(f"{role}: {content} (rewritten: {rewritten})")
            else:
                lines.append(f"{role}: {content}")
        return "\n".join(lines)

    def _update_conversation_metadata(
        self,
        conversation_id: str,
        paper_id: str | None,
        last_rewritten_question: str,
    ) -> None:
        conversation = self.store.get_conversation(conversation_id)
        if not conversation:
            return
        metadata = _metadata(conversation.get("metadata"))
        metadata["kind"] = "qa"
        metadata["last_rewritten_question"] = last_rewritten_question
        if paper_id:
            metadata["default_paper_id"] = paper_id
        self.store.update_conversation_metadata(conversation_id, _metadata_json(metadata))

    def _maybe_update_summary(
        self,
        conversation_id: str,
        rewritten_question: str,
        sources: list[dict],
    ) -> None:
        count = self.store.count_messages(conversation_id)
        if count < self.summary_message_threshold:
            return

        conversation = self.store.get_conversation(conversation_id)
        if not conversation:
            return
        metadata = _metadata(conversation.get("metadata"))
        previous_count = int(metadata.get("summary_message_count") or 0)
        if count - previous_count < self.summary_min_new_messages:
            return

        recent_turns = self._format_recent_turns(
            self.store.get_messages(conversation_id, limit=self.recent_message_limit)
        )
        source_notes = self._source_notes(sources)
        try:
            prompt = build_summary_update_prompt(
                previous_summary=str(metadata.get("summary") or ""),
                recent_turns=recent_turns,
                rewritten_question=rewritten_question,
                source_notes=source_notes,
            )
            summary = self.llm_client.generate_text(prompt).strip()
        except Exception as exc:
            logger.warning("QA summary update failed: %s", exc)
            return
        if not summary:
            return
        metadata["summary"] = summary
        metadata["summary_updated_at"] = time.time()
        metadata["summary_message_count"] = count
        self.store.update_conversation_metadata(conversation_id, _metadata_json(metadata))

    def _source_notes(self, sources: list[dict]) -> str:
        notes = []
        for source in sources[:5]:
            paper = source.get("paper_id") or "unknown"
            section = source.get("section_path") or source.get("section") or "unknown"
            page = source.get("page_range") or source.get("page_number") or "?"
            notes.append(f"{paper} {section} p.{page}")
        return "\n".join(notes)
```

- [ ] **Step 4: Run service tests**

Run:

```powershell
& 'D:\Hcworkspace\Anoconda3\envs\research_agent\python.exe' -m pytest tests/test_qa_memory.py -q --basetemp .pytest-tmp-qa-thread-memory
```

Expected: PASS.

- [ ] **Step 5: Commit Task 3**

Run:

```powershell
git add app/services/qa_memory.py tests/test_qa_memory.py
git commit -m "feat: add QA memory service"
```

Expected: commit succeeds.

---

### Task 4: Integrate QA Thread Memory Into `POST /qa`

**Files:**
- Modify: `app/schemas.py`
- Modify: `app/main.py`
- Create: `tests/test_qa_thread_api.py`

- [ ] **Step 1: Add failing API tests**

Create `tests/test_qa_thread_api.py`:

```python
import os
import sys
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from fastapi.testclient import TestClient

from app.main import app
from app.routers.conversations import set_memory_store
from app.services.memory_store import MemoryStore


def _qa_payload(answer="grounded answer"):
    return {
        "question": "rewritten question",
        "answer": answer,
        "sources": [
            {
                "paper_id": "paper_001",
                "title": "Grounding DINO",
                "section": "Results",
                "chunk_id": "chunk_1",
                "content": "52.5 AP on COCO zero-shot.",
                "score": 0.9,
            }
        ],
        "retrieval_time": 0.1,
        "llm_time": 0.2,
    }


def test_qa_endpoint_creates_conversation_and_returns_thread_fields(tmp_path):
    store = MemoryStore(tmp_path / "memory.db")
    set_memory_store(store)
    client = TestClient(app)
    llm = MagicMock()
    llm.generate_text.return_value = "Grounding DINO zero-shot metrics?"

    with patch("app.main._get_llm_client", return_value=llm), patch(
        "app.main.answer_question", return_value=_qa_payload()
    ) as mock_answer:
        resp = client.post(
            "/qa",
            json={
                "question": "它的 zero-shot 指标是多少？",
                "paper_id": "paper_001",
                "top_k": 5,
            },
        )

    assert resp.status_code == 200
    data = resp.json()
    assert data["conversation_id"]
    assert data["rewritten_question"] == "Grounding DINO zero-shot metrics?"
    assert data["answer"] == "grounded answer"
    mock_answer.assert_called_once()
    assert mock_answer.call_args.kwargs["question"] == "Grounding DINO zero-shot metrics?"
    assert store.count_messages(data["conversation_id"]) == 2
    set_memory_store(None)
    store.close()


def test_qa_endpoint_reuses_conversation_id(tmp_path):
    store = MemoryStore(tmp_path / "memory.db")
    set_memory_store(store)
    client = TestClient(app)
    llm = MagicMock()
    llm.generate_text.side_effect = ["First rewritten", "Second rewritten"]

    with patch("app.main._get_llm_client", return_value=llm), patch(
        "app.main.answer_question", return_value=_qa_payload()
    ):
        first = client.post("/qa", json={"question": "First?", "top_k": 5}).json()
        second = client.post(
            "/qa",
            json={
                "question": "它呢？",
                "top_k": 5,
                "conversation_id": first["conversation_id"],
            },
        ).json()

    assert second["conversation_id"] == first["conversation_id"]
    assert second["rewritten_question"] == "Second rewritten"
    assert store.count_messages(first["conversation_id"]) == 4
    set_memory_store(None)
    store.close()


def test_qa_endpoint_rejects_deleted_conversation(tmp_path):
    store = MemoryStore(tmp_path / "memory.db")
    set_memory_store(store)
    client = TestClient(app)

    resp = client.post(
        "/qa",
        json={"question": "Follow up?", "conversation_id": "missing"},
    )

    assert resp.status_code == 404
    set_memory_store(None)
    store.close()
```

- [ ] **Step 2: Run API tests to verify failure**

Run:

```powershell
& 'D:\Hcworkspace\Anoconda3\envs\research_agent\python.exe' -m pytest tests/test_qa_thread_api.py -q --basetemp .pytest-tmp-qa-thread-memory
```

Expected: FAIL because schema fields and `/qa` service wiring are missing.

- [ ] **Step 3: Extend QA schemas**

In `app/schemas.py`, change QA models to:

```python
class QARequest(BaseModel):
    question: str
    paper_id: str | None = None
    top_k: int = 5
    conversation_id: str | None = None


class QAResponse(BaseModel):
    question: str
    rewritten_question: str | None = None
    answer: str
    sources: list[SourceItem]
    conversation_id: str | None = None
```

- [ ] **Step 4: Wire `/qa` through `QAMemoryService`**

In `app/main.py`, import the conversation store and QA memory service near other service imports:

```python
from app.routers.conversations import get_memory_store
from app.services.qa_memory import QAMemoryService
```

Replace `qa_endpoint()` with:

```python
@app.post("/qa", response_model=QAResponse)
async def qa_endpoint(req: QARequest):
    reranker = _get_reranker()
    retriever = _get_retriever()
    service = QAMemoryService(
        store=get_memory_store(),
        llm_client=_get_llm_client(),
    )

    def run_answer_question(
        question: str,
        paper_id: str | None = None,
        top_k: int = 5,
        conversation_summary: str = "",
        recent_turns: str = "",
        original_question: str | None = None,
    ):
        return answer_question(
            question=question,
            vector_store=_get_vector_store(),
            embedding_client=_get_embedding_client(),
            llm_client=_get_llm_client(),
            paper_id=paper_id,
            top_k=settings.rerank_top_k if reranker else top_k,
            reranker=reranker,
            recall_top_k=settings.rerank_recall_top_k if reranker else None,
            retriever=retriever,
            conversation_summary=conversation_summary,
            recent_turns=recent_turns,
            original_question=original_question,
        )

    try:
        result = service.ask(
            question=req.question,
            paper_id=req.paper_id,
            top_k=req.top_k,
            conversation_id=req.conversation_id,
            answer_fn=run_answer_question,
        )
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except RuntimeError as e:
        raise HTTPException(status_code=502, detail=str(e)) from e

    return QAResponse(
        question=result["question"],
        rewritten_question=result.get("rewritten_question"),
        answer=result["answer"],
        sources=[SourceItem(**s) for s in result["sources"]],
        conversation_id=result.get("conversation_id"),
    )
```

- [ ] **Step 5: Extend `answer_question()` signature and prompt call**

In `app/services/paper_qa.py`, import the contextual builder:

```python
from app.prompts.qa_prompt import build_contextual_qa_prompt, build_qa_prompt
```

Extend `answer_question()` parameters:

```python
    conversation_summary: str = "",
    recent_turns: str = "",
    original_question: str | None = None,
```

Replace:

```python
    prompt = build_qa_prompt(question, context)
```

with:

```python
    if conversation_summary or recent_turns or original_question:
        prompt = build_contextual_qa_prompt(
            question=original_question or question,
            rewritten_question=question,
            context=context,
            conversation_summary=conversation_summary,
            recent_turns=recent_turns,
        )
    else:
        prompt = build_qa_prompt(question, context)
```

- [ ] **Step 6: Run backend QA memory tests**

Run:

```powershell
& 'D:\Hcworkspace\Anoconda3\envs\research_agent\python.exe' -m pytest tests/test_qa_memory.py tests/test_qa_thread_api.py tests/test_paper_qa.py tests/test_api_conversations.py -q --basetemp .pytest-tmp-qa-thread-memory
```

Expected: PASS.

- [ ] **Step 7: Commit Task 4**

Run:

```powershell
git add app/schemas.py app/main.py app/services/paper_qa.py tests/test_qa_thread_api.py
git commit -m "feat: route QA through thread memory"
```

Expected: commit succeeds.

---

### Task 5: Add Frontend Conversation API Client And Types

**Files:**
- Create: `frontend/src/api/conversations.ts`
- Modify: `frontend/src/api/qa.ts`
- Modify: `frontend/src/api/types.ts`

- [ ] **Step 1: Extend frontend types**

In `frontend/src/api/types.ts`, replace `QAResponse` and add conversation types:

```ts
export interface QAResponse {
  question: string;
  rewritten_question?: string | null;
  answer: string;
  sources: SourceItem[];
  conversation_id?: string | null;
}

export interface ConversationListItem {
  id: string;
  title: string;
  created_at: number;
  updated_at: number;
  metadata: Record<string, unknown>;
}

export interface ConversationMessage {
  id: string;
  role: "user" | "assistant" | string;
  content: string;
  created_at: number;
  metadata: Record<string, unknown>;
}

export interface ConversationDetail {
  conversation: ConversationListItem;
  messages: ConversationMessage[];
}

export interface ConversationListResponse {
  conversations: ConversationListItem[];
  total: number;
}

export interface DeleteConversationResponse {
  deleted: boolean;
  conversation_id: string;
}
```

- [ ] **Step 2: Update QA API request type**

Replace `frontend/src/api/qa.ts` with:

```ts
import { apiJson } from "./client";
import type { QAResponse } from "./types";

export interface AskQuestionRequest {
  question: string;
  paper_id?: string | null;
  top_k?: number;
  conversation_id?: string | null;
}

export function askQuestion(request: AskQuestionRequest) {
  return apiJson<QAResponse>("/qa", { body: request });
}
```

- [ ] **Step 3: Add conversation API client**

Create `frontend/src/api/conversations.ts`:

```ts
import { apiDelete, apiGet } from "./client";
import type { ConversationDetail, ConversationListResponse, DeleteConversationResponse } from "./types";

export function listConversations(kind?: string, limit = 8) {
  const params = new URLSearchParams();
  params.set("limit", String(limit));
  if (kind) params.set("kind", kind);
  return apiGet<ConversationListResponse>(`/api/conversations?${params.toString()}`);
}

export function getConversation(conversationId: string) {
  return apiGet<ConversationDetail>(`/api/conversations/${conversationId}`);
}

export function deleteConversation(conversationId: string) {
  return apiDelete<DeleteConversationResponse>(`/api/conversations/${conversationId}`);
}
```

- [ ] **Step 4: Run frontend type check**

Run:

```powershell
Set-Location frontend
npm run lint
```

Expected: PASS or only failures unrelated to these new files. If an unrelated failure appears, capture the file and error in the implementation notes before continuing.

- [ ] **Step 5: Commit Task 5**

Run:

```powershell
git add frontend/src/api/types.ts frontend/src/api/qa.ts frontend/src/api/conversations.ts
git commit -m "feat: add QA conversation frontend API"
```

Expected: commit succeeds.

---

### Task 6: Convert QA Page To Server-Backed Threads

**Files:**
- Modify: `frontend/src/pages/qa/QaPage.tsx`
- Modify: `frontend/src/pages/qa/QaPage.test.tsx`

- [ ] **Step 1: Replace frontend QA tests with server-backed behavior**

Replace `frontend/src/pages/qa/QaPage.test.tsx` with:

```tsx
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { QaPage } from "./QaPage";
import * as conversationApi from "../../api/conversations";
import * as papersApi from "../../api/papers";
import * as qaApi from "../../api/qa";
import type { ConversationDetail, ConversationListResponse, QAResponse } from "../../api/types";

vi.mock("../../api/papers", () => ({ getPapers: vi.fn() }));
vi.mock("../../api/qa", () => ({ askQuestion: vi.fn() }));
vi.mock("../../api/conversations", () => ({
  listConversations: vi.fn(),
  getConversation: vi.fn(),
  deleteConversation: vi.fn()
}));

function renderPage() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <QaPage />
    </QueryClientProvider>
  );
}

function deferred<T>() {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>((innerResolve) => {
    resolve = innerResolve;
  });
  return { promise, resolve };
}

const qaResponse: QAResponse = {
  question: "What is attention?",
  rewritten_question: "What is attention in Attention Survey?",
  answer: "Attention weighs token interactions.",
  conversation_id: "conv_1",
  sources: [
    {
      paper_id: "paper_001",
      title: "Attention Survey",
      section: "Methods",
      chunk_id: "chunk_001",
      content: "Attention assigns weights.",
      score: 0.9
    }
  ]
};

const emptyConversations: ConversationListResponse = {
  conversations: [],
  total: 0
};

beforeEach(() => {
  vi.clearAllMocks();
  localStorage.clear();
  vi.mocked(papersApi.getPapers).mockResolvedValue({
    count: 1,
    papers: [{ paper_id: "paper_001", title: "Attention Survey", abstract: "Abstract" }]
  });
  vi.mocked(conversationApi.listConversations).mockResolvedValue(emptyConversations);
  vi.mocked(conversationApi.deleteConversation).mockResolvedValue({
    deleted: true,
    conversation_id: "conv_1"
  });
  vi.mocked(qaApi.askQuestion).mockResolvedValue(qaResponse);
});

describe("QaPage", () => {
  it("submits first QA request and stores returned conversation id", async () => {
    const user = userEvent.setup();
    renderPage();

    await user.type(screen.getByRole("textbox", { name: "Question" }), "What is attention?");
    await user.selectOptions(await screen.findByLabelText(/scope/i), "paper_001");
    await user.click(screen.getByRole("button", { name: "Send" }));

    await waitFor(() => expect(screen.getByText("Attention weighs token interactions.")).toBeInTheDocument());
    expect(vi.mocked(qaApi.askQuestion).mock.calls[0][0]).toEqual({
      question: "What is attention?",
      paper_id: "paper_001",
      top_k: 5,
      conversation_id: null
    });
    expect(localStorage.getItem("research-agent:qa:conversation-id:v1")).toBe("conv_1");
    expect(screen.getByText(/rewritten query/i)).toBeInTheDocument();
  });

  it("sends follow-up questions with the active conversation id", async () => {
    const user = userEvent.setup();
    renderPage();

    await user.type(screen.getByRole("textbox", { name: "Question" }), "What is attention?");
    await user.click(screen.getByRole("button", { name: "Send" }));
    await waitFor(() => expect(screen.getByText("Attention weighs token interactions.")).toBeInTheDocument());

    vi.mocked(qaApi.askQuestion).mockResolvedValueOnce({
      ...qaResponse,
      question: "What about metrics?",
      rewritten_question: "What metrics does Attention Survey report?",
      answer: "It reports accuracy."
    });
    await user.type(screen.getByRole("textbox", { name: "Question" }), "What about metrics?");
    await user.click(screen.getByRole("button", { name: "Send" }));

    await waitFor(() => expect(screen.getByText("It reports accuracy.")).toBeInTheDocument());
    expect(vi.mocked(qaApi.askQuestion).mock.calls[1][0]).toMatchObject({
      question: "What about metrics?",
      conversation_id: "conv_1"
    });
  });

  it("loads a recent QA conversation and restores sources", async () => {
    const user = userEvent.setup();
    vi.mocked(conversationApi.listConversations).mockResolvedValue({
      total: 1,
      conversations: [
        {
          id: "conv_1",
          title: "Saved QA",
          created_at: 1,
          updated_at: 2,
          metadata: { kind: "qa" }
        }
      ]
    });
    const detail: ConversationDetail = {
      conversation: {
        id: "conv_1",
        title: "Saved QA",
        created_at: 1,
        updated_at: 2,
        metadata: { kind: "qa" }
      },
      messages: [
        {
          id: "m1",
          role: "user",
          content: "Saved question?",
          created_at: 1,
          metadata: { kind: "qa_user", paper_id: "paper_001", top_k: 7 }
        },
        {
          id: "m2",
          role: "assistant",
          content: "Saved answer.",
          created_at: 2,
          metadata: {
            kind: "qa_assistant",
            status: "done",
            rewritten_question: "Standalone saved question?",
            sources: qaResponse.sources
          }
        }
      ]
    };
    vi.mocked(conversationApi.getConversation).mockResolvedValue(detail);
    renderPage();

    await user.click(await screen.findByRole("button", { name: /Saved QA/i }));

    expect(await screen.findByText("Saved question?")).toBeInTheDocument();
    expect(screen.getByText("Saved answer.")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Sources (1)" }));
    expect(screen.getByText("Attention assigns weights.")).toBeInTheDocument();
  });

  it("starts a new chat without reusing the previous conversation id", async () => {
    const user = userEvent.setup();
    renderPage();

    await user.type(screen.getByRole("textbox", { name: "Question" }), "What is attention?");
    await user.click(screen.getByRole("button", { name: "Send" }));
    await waitFor(() => expect(screen.getByText("Attention weighs token interactions.")).toBeInTheDocument());

    await user.click(screen.getByRole("button", { name: "New chat" }));
    await user.type(screen.getByRole("textbox", { name: "Question" }), "Fresh question?");
    await user.click(screen.getByRole("button", { name: "Send" }));

    expect(vi.mocked(qaApi.askQuestion).mock.calls[1][0]).toMatchObject({
      question: "Fresh question?",
      conversation_id: null
    });
  });

  it("clears the active conversation through the backend", async () => {
    const user = userEvent.setup();
    renderPage();

    await user.type(screen.getByRole("textbox", { name: "Question" }), "What is attention?");
    await user.click(screen.getByRole("button", { name: "Send" }));
    await waitFor(() => expect(screen.getByText("Attention weighs token interactions.")).toBeInTheDocument());

    await user.click(screen.getByRole("button", { name: "Clear conversation" }));

    expect(conversationApi.deleteConversation).toHaveBeenCalledWith("conv_1");
    expect(screen.queryByText("Attention weighs token interactions.")).not.toBeInTheDocument();
    expect(localStorage.getItem("research-agent:qa:conversation-id:v1")).toBeNull();
  });

  it("shows a thinking message while pending", async () => {
    const user = userEvent.setup();
    const pending = deferred<QAResponse>();
    vi.mocked(qaApi.askQuestion).mockReturnValue(pending.promise);
    renderPage();

    await user.type(screen.getByRole("textbox", { name: "Question" }), "What is attention?");
    await user.click(screen.getByRole("button", { name: "Send" }));

    expect(screen.getByText("What is attention?")).toBeInTheDocument();
    expect(screen.getByText(/model is retrieving sources/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Thinking" })).toBeDisabled();

    pending.resolve(qaResponse);
    await waitFor(() => expect(screen.getByText("Attention weighs token interactions.")).toBeInTheDocument());
  });
});
```

- [ ] **Step 2: Run QA page tests to verify failure**

Run:

```powershell
Set-Location frontend
npm test -- QaPage.test.tsx
```

Expected: FAIL because `QaPage` still uses local-only state and does not import conversation API.

- [ ] **Step 3: Update `QaPage.tsx` message types and imports**

At the top of `frontend/src/pages/qa/QaPage.tsx`, replace imports and storage constants with:

```tsx
import { FormEvent, useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { SendHorizontal, X } from "lucide-react";
import { askQuestion } from "../../api/qa";
import { deleteConversation, getConversation, listConversations } from "../../api/conversations";
import { getPapers } from "../../api/papers";
import type { ConversationDetail, ConversationMessage, SourceItem } from "../../api/types";
import { EmptyState } from "../../components/empty-state/EmptyState";
import { ErrorState } from "../../components/error-state/ErrorState";
import { PaperSelector } from "../../components/papers/PaperSelector";
import { MarkdownContent } from "../../components/common/MarkdownContent";

const QA_CONVERSATION_ID_KEY = "research-agent:qa:conversation-id:v1";
const MAX_VISIBLE_MESSAGES = 30;
```

Use this `QaMessage` type:

```tsx
type QaMessage =
  | {
      id: string;
      role: "user";
      content: string;
      created_at: string;
      paper_id: string | null;
      top_k: number;
    }
  | {
      id: string;
      role: "assistant";
      content: string;
      status: "thinking" | "done" | "error";
      created_at: string;
      sources: SourceItem[];
      rewritten_question?: string | null;
      error?: string;
      request: {
        question: string;
        paper_id: string | null;
        top_k: number;
      };
    };
```

- [ ] **Step 4: Add metadata helpers inside `QaPage.tsx`**

Add helper functions below `createMessageId()`:

```tsx
function loadStoredConversationId() {
  try {
    return localStorage.getItem(QA_CONVERSATION_ID_KEY);
  } catch {
    return null;
  }
}

function storeConversationId(conversationId: string | null) {
  try {
    if (conversationId) {
      localStorage.setItem(QA_CONVERSATION_ID_KEY, conversationId);
    } else {
      localStorage.removeItem(QA_CONVERSATION_ID_KEY);
    }
  } catch {
    // Browser storage is a convenience cache only.
  }
}

function stringMetadataValue(metadata: Record<string, unknown>, key: string) {
  const value = metadata[key];
  return typeof value === "string" ? value : null;
}

function numberMetadataValue(metadata: Record<string, unknown>, key: string, fallback: number) {
  const value = metadata[key];
  return typeof value === "number" ? value : fallback;
}

function sourcesMetadataValue(metadata: Record<string, unknown>) {
  const value = metadata.sources;
  return Array.isArray(value) ? (value as SourceItem[]) : [];
}

function mapConversationMessage(message: ConversationMessage): QaMessage | null {
  const createdAt = new Date(message.created_at * 1000).toISOString();
  if (message.role === "user") {
    return {
      id: message.id,
      role: "user",
      content: message.content,
      created_at: createdAt,
      paper_id: stringMetadataValue(message.metadata, "paper_id"),
      top_k: numberMetadataValue(message.metadata, "top_k", 5)
    };
  }
  if (message.role === "assistant") {
    const status = stringMetadataValue(message.metadata, "status") === "error" ? "error" : "done";
    return {
      id: message.id,
      role: "assistant",
      content: message.content,
      status,
      created_at: createdAt,
      sources: sourcesMetadataValue(message.metadata),
      rewritten_question: stringMetadataValue(message.metadata, "rewritten_question"),
      error: stringMetadataValue(message.metadata, "error") ?? undefined,
      request: {
        question: stringMetadataValue(message.metadata, "rewritten_question") ?? message.content,
        paper_id: stringMetadataValue(message.metadata, "paper_id"),
        top_k: numberMetadataValue(message.metadata, "top_k", 5)
      }
    };
  }
  return null;
}

function mapConversationDetail(detail: ConversationDetail) {
  return detail.messages
    .map(mapConversationMessage)
    .filter((message): message is QaMessage => message !== null)
    .slice(-MAX_VISIBLE_MESSAGES);
}
```

- [ ] **Step 5: Update state, queries, and mutations in `QaPage()`**

Inside `QaPage()`, replace the existing `storedState` and state initialization block with:

```tsx
  const queryClient = useQueryClient();
  const [question, setQuestion] = useState("");
  const [activeConversationId, setActiveConversationId] = useState<string | null>(() => loadStoredConversationId());
  const [paperId, setPaperId] = useState("");
  const [topK, setTopK] = useState(5);
  const [messages, setMessages] = useState<QaMessage[]>([]);
```

Add conversations query:

```tsx
  const conversationsQuery = useQuery({
    queryKey: ["qa-conversations"],
    queryFn: () => listConversations("qa", 8)
  });
```

Add active conversation load effect:

```tsx
  useEffect(() => {
    if (!activeConversationId) return;
    let cancelled = false;
    getConversation(activeConversationId)
      .then((detail) => {
        if (cancelled) return;
        setMessages(mapConversationDetail(detail));
        const lastUser = [...detail.messages].reverse().find((message) => message.role === "user");
        if (lastUser) {
          const paper = stringMetadataValue(lastUser.metadata, "paper_id");
          const restoredTopK = numberMetadataValue(lastUser.metadata, "top_k", 5);
          setPaperId(paper ?? "");
          setTopK(restoredTopK);
        }
      })
      .catch(() => {
        if (cancelled) return;
        setActiveConversationId(null);
        storeConversationId(null);
        setMessages([]);
      });
    return () => {
      cancelled = true;
    };
  }, [activeConversationId]);
```

Replace localStorage message persistence effect with:

```tsx
  useEffect(() => {
    storeConversationId(activeConversationId);
  }, [activeConversationId]);
```

Add delete mutation:

```tsx
  const deleteMutation = useMutation({
    mutationFn: deleteConversation,
    onSuccess: () => {
      setActiveConversationId(null);
      setMessages([]);
      setSourcePanel(null);
      storeConversationId(null);
      queryClient.invalidateQueries({ queryKey: ["qa-conversations"] });
    }
  });
```

- [ ] **Step 6: Update submit, New chat, and Clear conversation handlers**

In `submitQuestion`, include `conversation_id`:

```tsx
      {
        question: trimmedQuestion,
        paper_id: scopePaperId,
        top_k: scopeTopK,
        conversation_id: activeConversationId
      },
```

In `onSuccess`, set thread id and rewritten query:

```tsx
          if (result.conversation_id) {
            setActiveConversationId(result.conversation_id);
            storeConversationId(result.conversation_id);
          }
          queryClient.invalidateQueries({ queryKey: ["qa-conversations"] });
          setMessages((current) =>
            current.map((message) =>
              message.id === assistantMessageId && message.role === "assistant"
                ? {
                    ...message,
                    content: result.answer,
                    status: "done",
                    sources: result.sources,
                    rewritten_question: result.rewritten_question,
                    request: {
                      ...message.request,
                      question: result.question
                    }
                  }
                : message
            )
          );
```

Add:

```tsx
  const startNewChat = () => {
    setActiveConversationId(null);
    setMessages([]);
    setSourcePanel(null);
    storeConversationId(null);
  };
```

Replace `clearConversation` with:

```tsx
  const clearConversation = () => {
    if (activeConversationId) {
      deleteMutation.mutate(activeConversationId);
      return;
    }
    startNewChat();
  };
```

Add:

```tsx
  const loadConversation = (conversationId: string) => {
    setActiveConversationId(conversationId);
    storeConversationId(conversationId);
    setSourcePanel(null);
  };
```

- [ ] **Step 7: Update rendered controls and recent thread list**

In the header action area, render New chat and Clear conversation:

```tsx
        <div className="flex flex-wrap gap-2">
          <button
            type="button"
            onClick={startNewChat}
            disabled={qaMutation.isPending}
            className="rounded-md border border-line bg-panel px-3 py-2 text-sm font-medium text-muted hover:bg-surface hover:text-ink disabled:opacity-60"
          >
            New chat
          </button>
          <button
            type="button"
            onClick={clearConversation}
            disabled={!hasMessages || qaMutation.isPending || deleteMutation.isPending}
            className="rounded-md border border-line bg-panel px-3 py-2 text-sm font-medium text-muted hover:bg-surface hover:text-ink disabled:opacity-60"
          >
            Clear conversation
          </button>
        </div>
```

Above the message/source layout, add:

```tsx
      {conversationsQuery.data?.conversations.length ? (
        <section className="flex flex-wrap gap-2">
          {conversationsQuery.data.conversations.map((conversation) => (
            <button
              key={conversation.id}
              type="button"
              onClick={() => loadConversation(conversation.id)}
              className={`rounded-full border px-3 py-1.5 text-xs font-medium ${
                conversation.id === activeConversationId
                  ? "border-accent bg-accent text-white"
                  : "border-line bg-panel text-muted hover:bg-surface hover:text-ink"
              }`}
            >
              {conversation.title || "QA conversation"}
            </button>
          ))}
        </section>
      ) : null}
```

Inside assistant done rendering, before Sources button, add rewritten query disclosure:

```tsx
                    {message.rewritten_question && (
                      <details className="mt-4 rounded-md border border-line bg-surface px-3 py-2 text-xs text-muted">
                        <summary className="cursor-pointer font-medium text-ink">Rewritten query</summary>
                        <p className="mt-2 whitespace-pre-wrap">{message.rewritten_question}</p>
                      </details>
                    )}
```

- [ ] **Step 8: Run frontend QA tests**

Run:

```powershell
Set-Location frontend
npm test -- QaPage.test.tsx
```

Expected: PASS.

- [ ] **Step 9: Run frontend type check**

Run:

```powershell
Set-Location frontend
npm run lint
```

Expected: PASS.

- [ ] **Step 10: Commit Task 6**

Run:

```powershell
git add frontend/src/pages/qa/QaPage.tsx frontend/src/pages/qa/QaPage.test.tsx
git commit -m "feat: add QA thread UI"
```

Expected: commit succeeds.

---

### Task 7: Final Verification And Documentation Check

**Files:**
- Verify only unless failures require targeted fixes.

- [ ] **Step 1: Run focused backend regression tests**

Run:

```powershell
& 'D:\Hcworkspace\Anoconda3\envs\research_agent\python.exe' -m pytest tests/test_qa_memory.py tests/test_qa_thread_api.py tests/test_api_conversations.py tests/test_paper_qa.py tests/test_paper_qa_closed_client.py tests/test_openapi_schema.py -q --basetemp .pytest-tmp-qa-thread-memory
```

Expected: PASS.

- [ ] **Step 2: Run focused frontend tests**

Run:

```powershell
Set-Location frontend
npm test -- QaPage.test.tsx
```

Expected: PASS.

- [ ] **Step 3: Run frontend type check**

Run:

```powershell
Set-Location frontend
npm run lint
```

Expected: PASS.

- [ ] **Step 4: Check git diff scope**

Run:

```powershell
git status --short
git diff --stat
```

Expected:

- Only QA memory implementation files are modified or committed.
- `.claude/settings.json` may still appear as an unrelated pre-existing dirty file; do not stage it.

- [ ] **Step 5: Commit any final targeted fixes**

If Step 1-4 revealed a targeted QA memory fix, stage only the touched QA memory files:

```powershell
git add app/services/qa_memory.py app/prompts/qa_prompt.py app/services/memory_store.py app/routers/conversations.py app/schemas.py app/main.py app/services/paper_qa.py tests/test_qa_memory.py tests/test_qa_thread_api.py tests/test_api_conversations.py tests/test_paper_qa.py frontend/src/api/conversations.ts frontend/src/api/qa.ts frontend/src/api/types.ts frontend/src/pages/qa/QaPage.tsx frontend/src/pages/qa/QaPage.test.tsx
git commit -m "fix: stabilize QA thread memory"
```

Expected: commit succeeds if there were fixes; skip this step if there were no final fixes.

## Plan Self-Review Checklist

- Spec coverage:
  - Backend thread persistence: Task 1, Task 3, Task 4.
  - Query rewrite and prompt history: Task 2, Task 3, Task 4.
  - Summary plus recent turns: Task 2, Task 3.
  - Conversation API metadata/filtering/deletion: Task 1, Task 4.
  - React recent QA thread list and restore: Task 5, Task 6.
  - Error handling and graceful rewrite/summary fallback: Task 3, Task 4, Task 6.
  - Evidence boundary: Task 2 and Task 4 preserve current RAG sources as the only answer evidence.
- Red-flag scan:
  - Scanned for banned planning markers and vague implementation instructions; none remain.
- Type consistency:
  - Backend response field is `rewritten_question` and frontend type uses the same field.
  - Conversation metadata remains `Record<string, unknown>` on frontend and `dict[str, Any]` on backend.
  - Active thread id is consistently `conversation_id` in API payloads and `activeConversationId` in React state.
