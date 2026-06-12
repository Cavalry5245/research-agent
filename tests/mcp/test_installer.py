from app.mcp.installer import (
    build_zotero_mcp_command,
    check_zotero_mcp_installed,
    ensure_zotero_mcp_installed,
)


def test_build_zotero_mcp_command_uses_configured_executable():
    command = build_zotero_mcp_command(
        "D:/Hcworkspace/Anoconda3/envs/research_agent/Scripts/zotero-mcp.exe"
    )
    assert command == [
        "D:/Hcworkspace/Anoconda3/envs/research_agent/Scripts/zotero-mcp.exe"
    ]


def test_build_zotero_mcp_command_preserves_configured_arguments():
    command = build_zotero_mcp_command(
        '"D:/Hcworkspace/Anoconda3/envs/research_agent/python.exe" -m zotero_mcp.cli'
    )
    assert command == [
        "D:/Hcworkspace/Anoconda3/envs/research_agent/python.exe",
        "-m",
        "zotero_mcp.cli",
    ]


def test_build_zotero_mcp_command_falls_back_to_path():
    assert build_zotero_mcp_command("") == ["zotero-mcp"]


def test_check_zotero_mcp_installed_returns_bool():
    assert isinstance(check_zotero_mcp_installed(), bool)


def test_ensure_zotero_mcp_installed_does_not_install_obsolete_package(monkeypatch):
    calls = []

    def fake_run(*args, **kwargs):
        calls.append(args[0])
        raise FileNotFoundError("missing")

    monkeypatch.setattr("app.mcp.installer.subprocess.run", fake_run)

    success, error = ensure_zotero_mcp_installed("missing-zotero-mcp")

    assert success is False
    assert "third_party/zotero-mcp" in error
    assert calls == [["missing-zotero-mcp", "version"]]
