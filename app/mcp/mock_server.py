from __future__ import annotations

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("ResearchAgent Mock MCP")


@mcp.tool(name="mock_echo")
def mock_echo(message: str) -> dict[str, str]:
    return {"message": message}


@mcp.tool(name="mock_fail")
def mock_fail() -> dict[str, str]:
    raise RuntimeError("mock failure")


def main() -> None:
    mcp.run("stdio")


if __name__ == "__main__":
    main()
