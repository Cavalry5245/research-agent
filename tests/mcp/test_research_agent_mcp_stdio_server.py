from app.mcp.client_manager import MCPClientManager
from app.mcp.schemas import MCPServerConfig, MCPToolCall
from app.mcp.tool_proxy import MCPToolProxy


def test_research_agent_mcp_stdio_server_lists_tools():
    manager = MCPClientManager()
    manager.start_server(
        MCPServerConfig(
            name="research-agent",
            command=["python", "-m", "app.research_workflow.mcp_stdio_server"],
        )
    )
    proxy = MCPToolProxy(manager)

    try:
        tools = proxy.list_available_tools()
    finally:
        manager.shutdown_all()

    assert "research_agent_list_runs" in tools["research-agent"]
    assert "research_agent_list_papers" in tools["research-agent"]
    assert "research_agent_get_run_trace" in tools["research-agent"]
    assert "research_agent_export_knowledge_pack" in tools["research-agent"]
    assert "research_agent_search_chunks" in tools["research-agent"]
    assert "research_agent_answer_question" in tools["research-agent"]
    assert "research_agent_compare_papers" in tools["research-agent"]


def test_research_agent_mcp_stdio_server_calls_list_runs():
    manager = MCPClientManager()
    manager.start_server(
        MCPServerConfig(
            name="research-agent",
            command=["python", "-m", "app.research_workflow.mcp_stdio_server"],
        )
    )
    proxy = MCPToolProxy(manager)

    try:
        result = proxy.call_tool(
            MCPToolCall(
                server_name="research-agent",
                tool_name="research_agent_list_runs",
            )
        )
    finally:
        manager.shutdown_all()

    assert result.status == "success"
    assert isinstance(result.result, dict)
    assert isinstance(result.result["runs"], list)
