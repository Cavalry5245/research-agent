import os
import sys
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


# ── PaperResearchAgent tests ─────────────────────────────────────────────────


def test_agent_creation():
    from app.agents.paper_research_agent import PaperResearchAgent
    agent = PaperResearchAgent()
    assert agent.tool_count == 6
    assert "qa" in agent.tool_names
    assert "upload_paper" in agent.tool_names
    assert "compare_papers" in agent.tool_names


def test_agent_creation_with_extra_tools():
    from app.agents.paper_research_agent import PaperResearchAgent
    from app.agents.tools.base import BaseTool, ToolParameter, ToolResult

    class CustomTool(BaseTool):
        name = "custom_tool"
        description = "A custom tool"

        @property
        def parameters(self):
            return [ToolParameter(name="x", type="string", description="x")]

        def execute(self, **kwargs):
            return ToolResult(success=True, data={"result": "ok"})

    agent = PaperResearchAgent(extra_tools=[CustomTool()])
    assert agent.tool_count == 7
    assert "custom_tool" in agent.tool_names


def test_get_agent_singleton():
    from app.agents.paper_research_agent import PaperResearchAgent, get_agent

    # Reset singleton
    import app.agents.paper_research_agent as mod
    mod._agent_instance = None

    a1 = get_agent()
    a2 = get_agent()
    assert a1 is a2
    mod._agent_instance = None


@patch("app.agents.paper_research_agent.create_agent")
def test_agent_execute(mock_create_agent):
    from app.agents.paper_research_agent import PaperResearchAgent

    mock_graph = MagicMock()
    mock_msg = MagicMock()
    mock_msg.content = "分析结果：这篇论文提出了新的方法..."
    mock_graph.invoke.return_value = {"messages": [mock_msg]}
    mock_create_agent.return_value = mock_graph

    agent = PaperResearchAgent()
    result = agent.execute("帮我分析 paper_001 的核心创新")

    assert result["task"] == "帮我分析 paper_001 的核心创新"
    assert "分析结果" in result["answer"]
    mock_graph.invoke.assert_called_once()


@patch("app.agents.paper_research_agent.create_agent")
def test_agent_execute_with_history(mock_create_agent):
    from app.agents.paper_research_agent import PaperResearchAgent

    mock_graph = MagicMock()
    mock_msg = MagicMock()
    mock_msg.content = "根据之前的讨论，这篇论文的方法..."
    mock_graph.invoke.return_value = {"messages": [mock_msg]}
    mock_create_agent.return_value = mock_graph

    agent = PaperResearchAgent()
    history = [
        {"role": "user", "content": "有哪些关于 VLM 的论文？"},
        {"role": "assistant", "content": "找到了 3 篇相关论文。"},
    ]
    result = agent.execute("详细分析第一篇", chat_history=history)

    assert result["task"] == "详细分析第一篇"
    assert "方法" in result["answer"]


@patch("app.agents.paper_research_agent.create_agent")
def test_agent_stream(mock_create_agent):
    from app.agents.paper_research_agent import PaperResearchAgent

    mock_graph = MagicMock()
    mock_graph.stream.return_value = iter([
        {"agent": {"messages": [MagicMock()]}},
    ])
    mock_create_agent.return_value = mock_graph

    agent = PaperResearchAgent()
    chunks = list(agent.stream("分析论文"))
    assert len(chunks) > 0