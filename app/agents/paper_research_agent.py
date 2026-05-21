import logging
import time
from typing import Any

from langchain.agents import create_agent
from langchain_openai import ChatOpenAI

from app.agents.langchain_adapter import convert_all_tools
from app.agents.prompts.agent_execution import AGENT_SYSTEM_PROMPT
from app.agents.tools.base import BaseTool
from app.agents.tools.paper_tools import (
    ComparePapersTool,
    ExportMarkdownTool,
    GenerateNoteTool,
    IndexPaperTool,
    QATool,
    UploadPaperTool,
)
from app.agents.tools.registry import ToolRegistry
from app.config import settings

logger = logging.getLogger(__name__)


class PaperResearchAgent:
    """Main agent that orchestrates paper research tasks.

    Wraps LangGraph create_react_agent for tool calling with conversation memory.
    """

    def __init__(self, extra_tools: list[BaseTool] | None = None):
        self._registry = ToolRegistry()
        self._register_default_tools()
        if extra_tools:
            self._registry.register_all(extra_tools)

        self._lc_tools = convert_all_tools(self._registry.list_tools())
        self._llm = self._build_llm()
        self._graph = create_agent(
            model=self._llm,
            tools=self._lc_tools,
            system_prompt=AGENT_SYSTEM_PROMPT,
        )

    def _build_llm(self) -> ChatOpenAI:
        return ChatOpenAI(
            base_url=settings.llm_base_url,
            api_key=settings.llm_api_key,
            model=settings.llm_model,
            temperature=0.3,
        )

    def _register_default_tools(self) -> None:
        self._registry.register_all([
            UploadPaperTool(),
            GenerateNoteTool(),
            IndexPaperTool(),
            QATool(),
            ComparePapersTool(),
            ExportMarkdownTool(),
        ])

    @property
    def tool_names(self) -> list[str]:
        return [t.name for t in self._registry.list_tools()]

    @property
    def tool_count(self) -> int:
        return len(self._registry.list_tools())

    def execute(self, task: str, chat_history: list[dict[str, str]] | None = None) -> dict[str, Any]:
        """Execute a user task and return the final answer.

        Args:
            task: User's natural language task description
            chat_history: Optional list of prior messages with 'role' and 'content'

        Returns:
            dict with keys: task, answer, messages
        """
        messages = []
        if chat_history:
            for m in chat_history:
                role = m.get("role", "user")
                content = m.get("content", "")
                if role == "user":
                    from langchain_core.messages import HumanMessage
                    messages.append(HumanMessage(content=content))
                else:
                    from langchain_core.messages import AIMessage
                    messages.append(AIMessage(content=content))

        from langchain_core.messages import HumanMessage
        messages.append(HumanMessage(content=task))

        logger.info("Agent executing task: %s", task[:100])
        started = time.perf_counter()
        result = self._graph.invoke({"messages": messages})
        duration_ms = (time.perf_counter() - started) * 1000
        logger.info(
            "agent_execute_completed",
            extra={
                "ra_duration_ms": round(duration_ms, 2),
                "ra_tools_count": self.tool_count,
                "ra_messages_count": len(result.get("messages", [])),
            },
        )

        # Extract the final AI response
        final_msg = result["messages"][-1]
        answer = final_msg.content if hasattr(final_msg, "content") else str(final_msg)

        return {
            "task": task,
            "answer": answer,
            "messages": result["messages"],
        }

    def stream(self, task: str, chat_history: list[dict[str, str]] | None = None):
        """Stream agent execution steps."""
        messages = []
        if chat_history:
            from langchain_core.messages import AIMessage, HumanMessage
            for m in chat_history:
                role = m.get("role", "user")
                content = m.get("content", "")
                if role == "user":
                    messages.append(HumanMessage(content=content))
                else:
                    messages.append(AIMessage(content=content))

        from langchain_core.messages import HumanMessage
        messages.append(HumanMessage(content=task))
        return self._graph.stream({"messages": messages})


# Singleton factory for the FastAPI layer
_agent_instance: PaperResearchAgent | None = None


def get_agent() -> PaperResearchAgent:
    global _agent_instance
    if _agent_instance is None:
        _agent_instance = PaperResearchAgent()
    return _agent_instance