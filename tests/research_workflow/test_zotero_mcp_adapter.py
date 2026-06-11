from app.research_workflow.zotero_mcp_adapter import ZoteroMCPAdapter
from app.mcp.tool_proxy import MCPToolProxy
from app.mcp.client_manager import MCPClientManager

def test_adapter_init():
    manager = MCPClientManager()
    proxy = MCPToolProxy(manager)
    adapter = ZoteroMCPAdapter(proxy)
    assert adapter is not None

def test_list_collection_items_structure():
    # Test the method signature exists
    manager = MCPClientManager()
    proxy = MCPToolProxy(manager)
    adapter = ZoteroMCPAdapter(proxy)

    # Method should exist and return list
    result = adapter.list_collection_items("test_id")
    assert isinstance(result, list)
