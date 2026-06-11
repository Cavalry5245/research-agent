from app.research_workflow.zotero_mcp_adapter import ZoteroMCPAdapter
from app.mcp.tool_proxy import MCPToolProxy
from app.mcp.client_manager import MCPClientManager

def test_adapter_init():
    manager = MCPClientManager()
    proxy = MCPToolProxy(manager)
    adapter = ZoteroMCPAdapter(proxy)
    assert adapter is not None
