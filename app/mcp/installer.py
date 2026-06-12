from __future__ import annotations

import logging
import shlex
import subprocess

logger = logging.getLogger(__name__)


def build_zotero_mcp_command(configured_command: str) -> list[str]:
    """Resolve the Zotero MCP command from config or PATH."""
    configured = configured_command.strip()
    if configured:
        return shlex.split(configured, posix=True)
    return ["zotero-mcp"]


def check_zotero_mcp_installed(command: str = "") -> bool:
    """Return whether a Zotero MCP executable can be started."""
    probe = [*build_zotero_mcp_command(command), "version"]
    try:
        result = subprocess.run(
            probe,
            capture_output=True,
            timeout=10,
            text=True,
        )
        return result.returncode == 0
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return False


def ensure_zotero_mcp_installed(command: str = "") -> tuple[bool, str]:
    """Check Zotero MCP availability without installing obsolete packages."""
    if check_zotero_mcp_installed(command):
        return True, ""
    return (
        False,
        "zotero-mcp is not available. Set ZOTERO_MCP_COMMAND to the zotero-mcp executable "
        "or install the editable third_party/zotero-mcp package.",
    )
