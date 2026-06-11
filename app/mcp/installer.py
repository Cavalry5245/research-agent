from __future__ import annotations
import subprocess
import logging

logger = logging.getLogger(__name__)


def check_zotero_mcp_installed() -> bool:
    """Check if zotero-mcp-server is installed."""
    try:
        result = subprocess.run(
            ["pip", "show", "zotero-mcp-server"],
            capture_output=True,
            timeout=5,
            text=True
        )
        return result.returncode == 0
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return False


def install_zotero_mcp() -> bool:
    """Install zotero-mcp-server via pip."""
    try:
        logger.info("Installing zotero-mcp-server...")
        subprocess.run(
            ["pip", "install", "zotero-mcp-server"],
            check=True,
            timeout=120
        )
        logger.info("zotero-mcp-server installed successfully")
        return True
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as e:
        logger.error(f"Failed to install zotero-mcp-server: {e}")
        return False


def ensure_zotero_mcp_installed() -> bool:
    """Ensure zotero-mcp-server is installed, install if missing."""
    if check_zotero_mcp_installed():
        return True
    return install_zotero_mcp()
