"""Integration test: PaperResearchAgent with memory persistence."""

import os
import sys
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.services.memory_store import MemoryStore


def _make_mock_agent():
    """Create a PaperResearchAgent with mocked LLM and in-memory store."""
    store = MemoryStore(":memory:")

    mock_message = MagicMock()
    mock_message.content = "This is the agent response."

    mock_graph = MagicMock()
    mock_graph.invoke.return_value = {"messages": [mock_message]}

    with patch("app.agents.paper_research_agent.create_agent", return_value=mock_graph):
        with patch("app.agents.paper_research_agent.ChatOpenAI"):
            from app.agents.paper_research_agent import PaperResearchAgent

            agent = PaperResearchAgent(memory_store=store)

    return agent, store, mock_graph


def test_execute_creates_conversation_and_persists_messages():
    agent, store, _ = _make_mock_agent()

    result = agent.execute("What is RAG?")

    assert "conversation_id" in result
    cid = result["conversation_id"]

    messages = store.get_messages(cid)
    assert len(messages) == 2
    assert messages[0]["role"] == "user"
    assert messages[0]["content"] == "What is RAG?"
    assert messages[1]["role"] == "assistant"
    assert messages[1]["content"] == "This is the agent response."


def test_execute_reuses_conversation_id():
    agent, store, _ = _make_mock_agent()

    r1 = agent.execute("First question")
    cid = r1["conversation_id"]

    r2 = agent.execute("Second question", conversation_id=cid)
    assert r2["conversation_id"] == cid

    messages = store.get_messages(cid)
    assert len(messages) == 4
    assert messages[2]["content"] == "Second question"


def test_memory_subsystems_accessible():
    agent, store, _ = _make_mock_agent()

    agent.long_term.set_preference("language", "zh")
    assert agent.long_term.get_preference("language") == "zh"

    agent.long_term.record_reading("paper-1", "view")
    history = agent.long_term.get_reading_history()
    assert len(history) == 1

    assert agent.memory_store is store


def test_short_term_context_fed_to_graph_on_continuation():
    agent, store, mock_graph = _make_mock_agent()

    r1 = agent.execute("Hello")
    cid = r1["conversation_id"]

    agent.execute("Follow up", conversation_id=cid)

    call_args = mock_graph.invoke.call_args[0][0]
    input_messages = call_args["messages"]
    assert len(input_messages) >= 2
