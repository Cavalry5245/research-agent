"""
WSL compatibility patch for pyzotero local mode.

When ZOTERO_LOCAL_HOST is set, this patches pyzotero to use that host
instead of hardcoded localhost for local API connections.

Usage: Import this module before importing zotero_mcp client modules.
"""
import os


def apply_wsl_patch():
    """Monkey-patch pyzotero to support custom localhost address for WSL."""
    custom_host = os.getenv("ZOTERO_LOCAL_HOST")
    if not custom_host:
        return  # No patch needed

    try:
        from pyzotero import zotero
    except ImportError:
        return  # pyzotero not installed

    # Patch the endpoint construction
    original_init = zotero.Zotero.__init__

    def patched_init(self, library_id=None, library_type=None, api_key=None, preserve_json_order=False, local=False, client=None):
        # Call original init
        original_init(self, library_id, library_type, api_key, preserve_json_order, local, client)

        # If local mode, replace localhost/127.0.0.1 with custom host in endpoint
        if local:
            if hasattr(self, 'endpoint'):
                self.endpoint = self.endpoint.replace('localhost', custom_host).replace('127.0.0.1', custom_host)
            # Also patch the base url if it exists
            if hasattr(self, 'endpoint_base'):
                self.endpoint_base = self.endpoint_base.replace('localhost', custom_host).replace('127.0.0.1', custom_host)

    # Apply patch
    zotero.Zotero.__init__ = patched_init

    # Also patch any module-level constants
    if hasattr(zotero, 'ZOTERO_URL'):
        zotero.ZOTERO_URL = zotero.ZOTERO_URL.replace('localhost', custom_host).replace('127.0.0.1', custom_host)


# Auto-apply on import
apply_wsl_patch()
