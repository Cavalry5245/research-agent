"""Thin stdio launcher for the external ``paper-search-mcp`` server.

The published ``paper-search-mcp`` package (0.1.x) ships no console script and
no ``main()`` entry point — its ``server.py`` only exposes a module-level
``mcp`` object and an ``if __name__ == "__main__"`` block. This launcher gives
it the same ``python -m app.mcp.<server>`` invocation pattern the project uses
for its own minimal MCP servers, so :class:`MCPServerConfig` can start it
without depending on a PATH-resident executable.

Importing ``paper_search_mcp.server`` instantiates all platform connectors at
module load; that cost is paid once when the stdio process starts.
"""

from __future__ import annotations

from paper_search_mcp.server import mcp


def main() -> None:
    mcp.run("stdio")


if __name__ == "__main__":
    main()
