from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field

from app.research_workflow.service import ResearchRunService


MCPToolStatus = Literal["completed", "failed"]


class MCPToolRequest(BaseModel):
    tool_name: str
    arguments: dict[str, Any] = Field(default_factory=dict)


class MCPToolResponse(BaseModel):
    tool_name: str
    status: MCPToolStatus
    result: Any = None
    error: str | None = None


class ResearchAgentMCPServer:
    def __init__(
        self,
        service: ResearchRunService,
        vector_search: Callable[[str, int], Any] | None = None,
        answer_question: Callable[[str, str | None], Any] | None = None,
        compare_papers: Callable[[list[str]], Any] | None = None,
    ) -> None:
        self._service = service
        self._vector_search = vector_search
        self._answer_question = answer_question
        self._compare_papers = compare_papers

    def call_tool(self, request: MCPToolRequest | dict[str, Any]) -> MCPToolResponse:
        req = (
            request
            if isinstance(request, MCPToolRequest)
            else MCPToolRequest.model_validate(request)
        )
        handler = {
            "research_agent.list_papers": self._list_papers,
            "research_agent.get_run_trace": self._get_run_trace,
            "research_agent.export_knowledge_pack": self._export_knowledge_pack,
            "research_agent.search_chunks": self._search_chunks,
            "research_agent.answer_question": self._answer_question_tool,
            "research_agent.compare_papers": self._compare_papers_tool,
        }.get(req.tool_name)
        if handler is None:
            return MCPToolResponse(
                tool_name=req.tool_name,
                status="failed",
                error=f"Unknown ResearchAgent tool: {req.tool_name}",
            )

        try:
            result = handler(req.arguments)
        except Exception as exc:
            return MCPToolResponse(
                tool_name=req.tool_name,
                status="failed",
                error=str(exc),
            )
        return MCPToolResponse(tool_name=req.tool_name, status="completed", result=result)

    def tool_health(self) -> list[dict[str, Any]]:
        return [
            {"tool_name": tool_name, "available": True, "provider": "research_agent"}
            for tool_name in (
                "research_agent.list_papers",
                "research_agent.get_run_trace",
                "research_agent.export_knowledge_pack",
                "research_agent.search_chunks",
                "research_agent.answer_question",
                "research_agent.compare_papers",
            )
        ]

    def _list_papers(self, arguments: dict[str, Any]) -> dict[str, Any]:
        run = self._service.get_run(_required(arguments, "run_id"))
        return {
            "run_id": run.run_id,
            "papers": [item.model_dump(mode="json") for item in run.paper_items],
        }

    def _get_run_trace(self, arguments: dict[str, Any]) -> dict[str, Any]:
        run = self._service.get_run(_required(arguments, "run_id"))
        trace_path = Path(run.output_dir) / "assets" / "trace.json"
        if trace_path.is_file():
            return json.loads(trace_path.read_text(encoding="utf-8"))
        return run.model_dump(mode="json")

    def _export_knowledge_pack(self, arguments: dict[str, Any]) -> dict[str, Any]:
        run = self._service.get_run(_required(arguments, "run_id"))
        return {
            "run_id": run.run_id,
            "output_dir": run.output_dir,
            "artifacts": [artifact.model_dump(mode="json") for artifact in run.artifacts],
        }

    def _search_chunks(self, arguments: dict[str, Any]) -> dict[str, Any]:
        query = _required(arguments, "query")
        top_k = int(arguments.get("top_k", 5))
        if self._vector_search is None:
            matches: Any = []
        else:
            matches = self._vector_search(query, top_k)
        return {"query": query, "top_k": top_k, "matches": matches}

    def _answer_question_tool(self, arguments: dict[str, Any]) -> dict[str, Any]:
        question = _required(arguments, "question")
        run_id = arguments.get("run_id")
        if self._answer_question is None:
            answer = "No question-answering backend is configured for this MCP facade."
        else:
            answer = self._answer_question(question, run_id)
        return {"question": question, "run_id": run_id, "answer": answer}

    def _compare_papers_tool(self, arguments: dict[str, Any]) -> dict[str, Any]:
        paper_ids = list(arguments.get("paper_ids") or [])
        if not paper_ids:
            raise ValueError("Missing required argument(s): paper_ids")
        if self._compare_papers is None:
            comparison: Any = {"paper_ids": paper_ids, "summary": "No comparison backend configured."}
        else:
            comparison = self._compare_papers(paper_ids)
        return {"paper_ids": paper_ids, "comparison": comparison}


def _required(arguments: dict[str, Any], name: str) -> Any:
    value = arguments.get(name)
    if value is None or value == "":
        raise ValueError(f"Missing required argument(s): {name}")
    return value
