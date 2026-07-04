# Paper Search MCP Health Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the `paper-search` MCP server visible in ResearchAgent's MCP Hub health payload and `/research-runs/tools/health` route.

**Architecture:** `app.research_workflow.mcp_health.build_mcp_hub_health()` is the single user-facing MCP health aggregator used by the Research Workflow tools-health route and the system status payload. The change adds `paper-search` to the existing stdio-server health path, reusing `_server_health()` instead of creating a new adapter because `paper-search` is already started and called through the generic MCP manager/proxy layer. Tests use a fake `_mcp_manager` so they verify the UI/API contract without starting a real external MCP process.

**Tech Stack:** Python, FastAPI `TestClient`, pytest, existing ResearchAgent MCP health helpers.

---

## Scope

This plan covers only the first integration cleanup step: exposing `paper-search` in MCP health / Dashboard data. It does not change the `paper-search-mcp` adapter, server launcher, dependency pin, workflow service registration, `.env.example`, or any real network/E2E paper search behavior.

## File Structure

- Modify: `tests/test_research_run_router.py`
  - Extend `test_tool_health_reports_mcp_state()` so the fake MCP manager includes both `zotero` and `paper-search`.
  - Assert that `Paper Search MCP Server` is present, running, has `provider == "mcp"`, `fallback_active is False`, and reports the discovered tool count.
- Modify: `app/research_workflow/mcp_health.py`
  - Add `tools.append(_server_health(manager, "paper-search", "Paper Search MCP Server"))` in `build_mcp_hub_health()`.
  - Add `paper-search` to the fallback provider/message mappings in `_server_health()`.
  - Add `paper-search` to the running-server `fallback_available` set.
- Verify only: `tests/test_system_status_endpoint.py`
  - No code change expected. The system status endpoint already delegates to `build_mcp_hub_health()` and separately tests that status checks do not start MCP servers.

## Acceptance Criteria

- `/research-runs/tools/health` includes a `Paper Search MCP Server` item when the service manager lists `paper-search`.
- The running `paper-search` health item has:
  - `provider == "mcp"`
  - `available is True`
  - `fallback_available is True`
  - `fallback_active is False`
  - `tool_count == 2` in the fake-manager route test
  - `state == "running"`
- When `paper-search` is not running, `build_mcp_hub_health()` returns a fallback-active `Paper Search MCP Server` item instead of omitting it.
- Existing Zotero, Semantic Scholar, arXiv, and ResearchAgent MCP health behavior remains unchanged.
- No real `paper-search-mcp` process is started by the unit/route tests.

### Task 1: Add Route-Level Failing Test

**Files:**
- Modify: `tests/test_research_run_router.py:168-201`
- Test: `tests/test_research_run_router.py::test_tool_health_reports_mcp_state`

- [ ] **Step 1: Replace the fake manager and assertions in the existing test**

Replace the body of `test_tool_health_reports_mcp_state()` with this complete version:

```python
def test_tool_health_reports_mcp_state(tmp_path, monkeypatch):
    service = _override_research_run_service(tmp_path, monkeypatch)

    class FakeManager:
        def list_servers(self):
            return ["zotero", "paper-search"]

        def list_tools(self, server_name):
            if server_name == "zotero":
                return ["zotero_get_collection_items", "zotero_get_item"]
            if server_name == "paper-search":
                return ["search_papers", "download_with_fallback"]
            raise AssertionError(f"unexpected server health check: {server_name}")

    service._mcp_manager = FakeManager()

    try:
        client = TestClient(app)
        response = client.get("/research-runs/tools/health")

        assert response.status_code == 200
        tools = response.json()["tools"]
        assert all("provider" in tool for tool in tools)
        assert all("fallback_active" in tool for tool in tools)
        assert all("state" in tool for tool in tools)

        zotero = next(
            tool for tool in tools if tool["tool_name"] == "Zotero MCP Server"
        )
        assert zotero["provider"] == "mcp"
        assert zotero["available"] is True
        assert zotero["fallback_active"] is False
        assert zotero["tool_count"] == 2
        assert "MCP tool(s) discovered" in zotero["message"]

        paper_search = next(
            tool for tool in tools if tool["tool_name"] == "Paper Search MCP Server"
        )
        assert paper_search["provider"] == "mcp"
        assert paper_search["available"] is True
        assert paper_search["fallback_available"] is True
        assert paper_search["fallback_active"] is False
        assert paper_search["tool_count"] == 2
        assert paper_search["state"] == "running"
        assert "MCP tool(s) discovered" in paper_search["message"]

        assert any(tool["tool_name"] == "ResearchAgent MCP Server" for tool in tools)
    finally:
        app.dependency_overrides.clear()
```

- [ ] **Step 2: Run the focused test and confirm it fails for the expected reason**

Run:

```powershell
& 'D:\Hcworkspace\Anoconda3\envs\research_agent\python.exe' -m pytest tests/test_research_run_router.py::test_tool_health_reports_mcp_state -q --basetemp .pytest-tmp-paper-search-health
```

Expected: the test fails because `Paper Search MCP Server` is not present in `tools`. The likely failure is `StopIteration` from this line:

```python
paper_search = next(
    tool for tool in tools if tool["tool_name"] == "Paper Search MCP Server"
)
```

### Task 2: Register Paper Search in MCP Health

**Files:**
- Modify: `app/research_workflow/mcp_health.py:37-46`
- Modify: `app/research_workflow/mcp_health.py:64-84`
- Test: `tests/test_research_run_router.py::test_tool_health_reports_mcp_state`

- [ ] **Step 1: Add the server health item to the MCP Hub list**

In `build_mcp_hub_health()`, replace the server append block with this exact block:

```python
    tools.append(_server_health(manager, "zotero", "Zotero MCP Server"))
    tools.append(
        _server_health(
            manager,
            "semantic-scholar",
            "Semantic Scholar MCP Server",
        )
    )
    tools.append(_server_health(manager, "arxiv", "arXiv MCP Server"))
    tools.append(_server_health(manager, "paper-search", "Paper Search MCP Server"))
    tools.append(_research_agent_server_health())
    return tools
```

- [ ] **Step 2: Add fallback provider and fallback message entries**

In `_server_health()`, replace the `fallback_provider` and `fallback_message` definitions with this exact code:

```python
    fallback_provider = {
        "zotero": "local_http",
        "semantic-scholar": "local_metadata",
        "arxiv": "local_metadata",
        "paper-search": "local_metadata",
    }.get(server_name, "local")
    fallback_message = {
        "zotero": "MCP server is not running; Zotero local HTTP fallback is active",
        "semantic-scholar": "MCP server is not running; local metadata fallback is active",
        "arxiv": "MCP server is not running; local paper metadata fallback is active",
        "paper-search": "MCP server is not running; unified paper search fallback is active",
    }.get(server_name, "MCP server is not running")
```

- [ ] **Step 3: Mark paper-search as having a fallback path**

In the running-server return payload inside `_server_health()`, replace the `fallback_available` line with this exact multi-line expression:

```python
                        "fallback_available": server_name
                        in {"zotero", "semantic-scholar", "arxiv", "paper-search"},
```

- [ ] **Step 4: Run the focused test and confirm it passes**

Run:

```powershell
& 'D:\Hcworkspace\Anoconda3\envs\research_agent\python.exe' -m pytest tests/test_research_run_router.py::test_tool_health_reports_mcp_state -q --basetemp .pytest-tmp-paper-search-health
```

Expected:

```text
1 passed
```

### Task 3: Add a Direct Fallback-State Test

**Files:**
- Modify: `tests/test_research_run_router.py`
- Test: `tests/test_research_run_router.py::test_tool_health_reports_paper_search_fallback_when_not_running`

- [ ] **Step 1: Add a direct route test for the not-running state**

Add this test immediately after `test_tool_health_reports_mcp_state()`:

```python
def test_tool_health_reports_paper_search_fallback_when_not_running(
    tmp_path, monkeypatch
):
    _override_research_run_service(tmp_path, monkeypatch)

    try:
        client = TestClient(app)
        response = client.get("/research-runs/tools/health")

        assert response.status_code == 200
        tools = response.json()["tools"]
        paper_search = next(
            tool for tool in tools if tool["tool_name"] == "Paper Search MCP Server"
        )
        assert paper_search["provider"] == "local_metadata"
        assert paper_search["available"] is False
        assert paper_search["fallback_available"] is True
        assert paper_search["fallback_active"] is True
        assert paper_search["tool_count"] == 0
        assert paper_search["state"] == "fallback_active"
        assert "unified paper search fallback is active" in paper_search["message"]
    finally:
        app.dependency_overrides.clear()
```

- [ ] **Step 2: Run the new fallback test**

Run:

```powershell
& 'D:\Hcworkspace\Anoconda3\envs\research_agent\python.exe' -m pytest tests/test_research_run_router.py::test_tool_health_reports_paper_search_fallback_when_not_running -q --basetemp .pytest-tmp-paper-search-health-fallback
```

Expected:

```text
1 passed
```

### Task 4: Run Regression Checks

**Files:**
- Verify: `tests/test_research_run_router.py`
- Verify: `tests/test_system_status_endpoint.py`
- Verify: `app/research_workflow/mcp_health.py`

- [ ] **Step 1: Run the route and status endpoint tests together**

Run:

```powershell
& 'D:\Hcworkspace\Anoconda3\envs\research_agent\python.exe' -m pytest tests/test_research_run_router.py tests/test_system_status_endpoint.py -q --basetemp .pytest-tmp-paper-search-health-suite
```

Expected: all selected tests pass. A pre-existing Starlette/FastAPI deprecation warning is acceptable if no test fails.

- [ ] **Step 2: Run the paper-search MCP adapter tests to check the broader integration remains intact**

Run:

```powershell
& 'D:\Hcworkspace\Anoconda3\envs\research_agent\python.exe' -m pytest tests/mcp/test_paper_search_mcp_adapter.py -q --basetemp .pytest-tmp-paper-search-adapter
```

Expected:

```text
16 passed
```

- [ ] **Step 3: Check diff hygiene**

Run:

```powershell
git diff -- app/research_workflow/mcp_health.py tests/test_research_run_router.py .env.example
git diff --check
```

Expected:

```text
git diff --check
```

prints no whitespace errors. Line-ending warnings such as `LF will be replaced by CRLF` are acceptable on this Windows workspace.

### Task 5: Commit the Health Visibility Change

**Files:**
- Stage: `app/research_workflow/mcp_health.py`
- Stage: `tests/test_research_run_router.py`
- Stage: `.env.example`

- [ ] **Step 1: Inspect final status**

Run:

```powershell
git status --short
```

Expected: the relevant files include:

```text
 M .env.example
 M app/research_workflow/mcp_health.py
 M tests/test_research_run_router.py
```

Other existing paper-search integration files may also be modified or untracked. Do not stage unrelated plan documents or temporary pytest directories unless the user explicitly asks.

- [ ] **Step 2: Stage only the reviewed health/config files**

Run:

```powershell
git add .env.example app/research_workflow/mcp_health.py tests/test_research_run_router.py
```

Expected: the three listed files are staged.

- [ ] **Step 3: Commit if the user wants this slice committed separately**

Run:

```powershell
git commit -m "feat: show paper-search MCP health"
```

Expected: one commit containing only the MCP health visibility change plus `.env.example` documentation.

## Self-Review

- Spec coverage: The plan covers the requested first step: `paper-search` appears in the same health payload consumed by MCP Hub / Dashboard and `/research-runs/tools/health`; it also covers the not-running fallback state.
- Placeholder scan: The plan contains no placeholder implementation steps; code blocks and commands are fully specified.
- Type consistency: The plan uses the existing `build_mcp_hub_health(service, storage_root)` flow, fake `_mcp_manager` methods `list_servers()` and `list_tools(server_name)`, and the existing health fields `tool_name`, `provider`, `available`, `fallback_available`, `fallback_active`, `message`, `tool_count`, and `state`.

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-07-04-paper-search-mcp-health.md`. Two execution options:

1. Subagent-Driven (recommended) - dispatch a fresh subagent per task, review between tasks, fast iteration.
2. Inline Execution - execute tasks in this session using `superpowers:executing-plans`, batch execution with checkpoints.

For this small change, Inline Execution is likely enough after user approval.
