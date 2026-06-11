from datetime import datetime, timezone

from app.research_workflow.mcp_server import MCPToolRequest, ResearchAgentMCPServer
from app.research_workflow.schemas import (
    ResearchRunCreateRequest,
    ResearchRunPaperItem,
)
from app.research_workflow.service import ResearchRunService
from app.research_workflow.store import FileResearchRunStore


def _server_with_run(tmp_path):
    store = FileResearchRunStore(tmp_path / "runs.json")
    service = ResearchRunService(store=store, vault_root=tmp_path / "vault")
    run = service.create_run(
        ResearchRunCreateRequest(collection_id="COLL123", collection_name="IRSTD")
    )
    now = datetime.now(timezone.utc)
    run = run.model_copy(
        update={
            "paper_items": [
                ResearchRunPaperItem(
                    item_id="zotero_A1",
                    title="Paper A",
                    zotero_item_id="A1",
                    paper_id="paper_001",
                    status="completed",
                    progress=1.0,
                    metadata={"year": 2025},
                    created_at=now,
                    updated_at=now,
                )
            ]
        }
    )
    store.upsert(run)
    server = ResearchAgentMCPServer(
        service=service,
        vector_search=lambda query, top_k: [{"text": query, "score": 0.9, "top_k": top_k}],
        answer_question=lambda question, run_id: f"Answered {question} for {run_id}",
    )
    return server, run


def test_research_agent_mcp_lists_papers(tmp_path):
    server, run = _server_with_run(tmp_path)

    response = server.call_tool(
        MCPToolRequest(
            tool_name="research_agent.list_papers",
            arguments={"run_id": run.run_id},
        )
    )

    assert response.status == "completed"
    assert response.result["papers"][0]["paper_id"] == "paper_001"


def test_research_agent_mcp_gets_run_trace(tmp_path):
    server, run = _server_with_run(tmp_path)

    response = server.call_tool(
        {"tool_name": "research_agent.get_run_trace", "arguments": {"run_id": run.run_id}}
    )

    assert response.status == "completed"
    assert response.result["run_id"] == run.run_id
    assert response.result["collection_id"] == "COLL123"


def test_research_agent_mcp_exports_knowledge_pack(tmp_path):
    server, run = _server_with_run(tmp_path)

    response = server.call_tool(
        {
            "tool_name": "research_agent.export_knowledge_pack",
            "arguments": {"run_id": run.run_id},
        }
    )

    assert response.status == "completed"
    assert response.result["output_dir"] == run.output_dir
    assert any(artifact["label"] == "Knowledge Pack" for artifact in response.result["artifacts"])


def test_research_agent_mcp_searches_chunks_with_callback(tmp_path):
    server, _run = _server_with_run(tmp_path)

    response = server.call_tool(
        {
            "tool_name": "research_agent.search_chunks",
            "arguments": {"query": "infrared target", "top_k": 2},
        }
    )

    assert response.status == "completed"
    assert response.result["matches"][0]["text"] == "infrared target"
    assert response.result["matches"][0]["top_k"] == 2


def test_research_agent_mcp_answers_question_with_callback(tmp_path):
    server, run = _server_with_run(tmp_path)

    response = server.call_tool(
        {
            "tool_name": "research_agent.answer_question",
            "arguments": {"question": "What is the method?", "run_id": run.run_id},
        }
    )

    assert response.status == "completed"
    assert response.result["answer"] == f"Answered What is the method? for {run.run_id}"


def test_research_agent_mcp_normalizes_errors(tmp_path):
    server, _run = _server_with_run(tmp_path)

    response = server.call_tool({"tool_name": "research_agent.list_papers", "arguments": {}})

    assert response.status == "failed"
    assert "run_id" in (response.error or "")


def test_research_agent_mcp_tool_health_lists_available_tools(tmp_path):
    server, _run = _server_with_run(tmp_path)

    names = {item["tool_name"] for item in server.tool_health()}

    assert "research_agent.list_papers" in names
    assert "research_agent.answer_question" in names
