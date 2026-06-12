from __future__ import annotations

from pathlib import Path
from typing import Any

from mcp.server.fastmcp import FastMCP

from app.config import settings
from app.research_workflow.mcp_server import MCPToolRequest, ResearchAgentMCPServer
from app.research_workflow.service import ResearchRunService
from app.research_workflow.store import FileResearchRunStore

mcp = FastMCP("ResearchAgent")


def _service() -> ResearchRunService:
    storage_root = Path(settings.metadata_dir).parent
    return ResearchRunService(
        store=FileResearchRunStore(storage_root / "research_runs.json"),
        vault_root=settings.obsidian_vault_root,
    )


def _server() -> ResearchAgentMCPServer:
    return ResearchAgentMCPServer(_service())


@mcp.tool(name="research_agent_list_runs")
def research_agent_list_runs() -> dict[str, Any]:
    service = _service()
    return {"runs": [run.model_dump(mode="json") for run in service.list_runs()]}


@mcp.tool(name="research_agent_list_papers")
def research_agent_list_papers(run_id: str) -> dict[str, Any]:
    return _server().call_tool(
        MCPToolRequest(
            tool_name="research_agent.list_papers",
            arguments={"run_id": run_id},
        )
    ).model_dump(mode="json")


@mcp.tool(name="research_agent_get_run_trace")
def research_agent_get_run_trace(run_id: str) -> dict[str, Any]:
    return _server().call_tool(
        MCPToolRequest(
            tool_name="research_agent.get_run_trace",
            arguments={"run_id": run_id},
        )
    ).model_dump(mode="json")


@mcp.tool(name="research_agent_export_knowledge_pack")
def research_agent_export_knowledge_pack(run_id: str) -> dict[str, Any]:
    return _server().call_tool(
        MCPToolRequest(
            tool_name="research_agent.export_knowledge_pack",
            arguments={"run_id": run_id},
        )
    ).model_dump(mode="json")


@mcp.tool(name="research_agent_search_chunks")
def research_agent_search_chunks(
    query: str,
    top_k: int = 5,
    paper_id: str | None = None,
) -> dict[str, Any]:
    return _server().call_tool(
        MCPToolRequest(
            tool_name="research_agent.search_chunks",
            arguments={"query": query, "top_k": top_k, "paper_id": paper_id},
        )
    ).model_dump(mode="json")


@mcp.tool(name="research_agent_answer_question")
def research_agent_answer_question(
    question: str,
    run_id: str | None = None,
    paper_id: str | None = None,
    top_k: int = 5,
) -> dict[str, Any]:
    return _server().call_tool(
        MCPToolRequest(
            tool_name="research_agent.answer_question",
            arguments={
                "question": question,
                "run_id": run_id,
                "paper_id": paper_id,
                "top_k": top_k,
            },
        )
    ).model_dump(mode="json")


@mcp.tool(name="research_agent_compare_papers")
def research_agent_compare_papers(paper_ids: list[str]) -> dict[str, Any]:
    return _server().call_tool(
        MCPToolRequest(
            tool_name="research_agent.compare_papers",
            arguments={"paper_ids": paper_ids},
        )
    ).model_dump(mode="json")


def main() -> None:
    mcp.run("stdio")


if __name__ == "__main__":
    main()
