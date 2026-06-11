from app.mcp.installer import check_zotero_mcp_installed

def test_check_installed():
    # This will return True/False depending on actual state
    result = check_zotero_mcp_installed()
    assert isinstance(result, bool)
