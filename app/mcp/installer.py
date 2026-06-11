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


def install_zotero_mcp(version: str = "0.1.0") -> tuple[bool, str]:
    """Install zotero-mcp-server via pip.

    Returns:
        (success: bool, error_message: str)
    """
    try:
        logger.info(f"Installing zotero-mcp-server=={version}...")
        result = subprocess.run(
            ["pip", "install", f"zotero-mcp-server=={version}"],
            check=True,
            timeout=180,
            capture_output=True,
            text=True
        )
        logger.info("zotero-mcp-server installed successfully")
        return True, ""
    except subprocess.CalledProcessError as e:
        error = f"Install failed: {e.stderr}"
        logger.error(error)
        return False, error
    except subprocess.TimeoutExpired:
        error = "Installation timeout (180s exceeded)"
        logger.error(error)
        return False, error
    except FileNotFoundError:
        error = "pip not found in PATH"
        logger.error(error)
        return False, error


def ensure_zotero_mcp_installed(version: str = "0.1.0") -> tuple[bool, str]:
    """Ensure zotero-mcp-server is installed, install if missing.

    Returns:
        (success: bool, error_message: str)
    """
    if check_zotero_mcp_installed():
        return True, ""
    return install_zotero_mcp(version)
