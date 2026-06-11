from __future__ import annotations
from typing import Any
from app.mcp.tool_proxy import MCPToolProxy
from app.research_workflow.zotero_intake import ZoteroCollectionItem


class ZoteroMCPAdapter:
    """Adapter for Zotero MCP server."""

    def __init__(self, tool_proxy: MCPToolProxy):
        self._proxy = tool_proxy
        self._server_name = "zotero"

    def list_collection_items(self, collection_id: str) -> list[ZoteroCollectionItem]:
        """
        List items in a Zotero collection via MCP.

        Note: This is a STUB implementation. Full implementation requires:
        1. MCPToolProxy.call_tool() method
        2. MCP protocol communication
        3. Response parsing

        For Phase 2, returns empty list to satisfy interface.
        """
        # TODO: Implement MCP tool call when protocol ready
        # call = MCPToolCall(
        #     server_name=self._server_name,
        #     tool_name="search_library",
        #     arguments={"collection": collection_id}
        # )
        # result = self._proxy.call_tool(call)
        # return self._parse_items(result.result)

        return []
