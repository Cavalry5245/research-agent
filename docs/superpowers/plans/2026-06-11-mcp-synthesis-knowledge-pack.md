# ResearchAgent M3-M4 MCP Synthesis Knowledge Pack Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Complete Milestone 3 and Milestone 4 by adding a local MCP-style tool hub, tested ResearchAgent tool facade, fallback adapters, synthesis artifacts, Obsidian-ready publishing, and UI visibility.

**Architecture:** Keep the core demo local-first and deterministic. Add small modules under `app/research_workflow/` that wrap existing ResearchRun, paper-processing, vector search, comparison, and Knowledge Pack behavior instead of rewriting older services. External integrations should report health and fall back to local behavior so a Zotero-to-Obsidian demo can run without live external MCP servers.

**Tech Stack:** Python 3.11, Pydantic, FastAPI, Streamlit, pytest, local file-backed ResearchRun store, JSONL tool-call tracing, Markdown Knowledge Pack outputs.

---

## Scope

Included:

- Tool registry with argument validation, normalized results, normalized errors, health reporting, fallback metadata, and standardized JSONL call records.
- Local fallback adapters for Zotero, Obsidian, Semantic Scholar, and arXiv.
- ResearchAgent MCP-style facade with at least five callable tools in tests.
- Run trace integration so tool calls include M3 registry fields.
- Deterministic multi-agent synthesis files for literature review, method matrix, research gaps, experiment plan, and reading roadmap.
- Obsidian-ready Knowledge Pack publishing through direct Markdown writes.
- Streamlit Tool Health and run-result visibility.
- Focused tests for each milestone and a final M3/M4 verification run.

Excluded:

- `.env` edits.
- Live external MCP server setup.
- Real Semantic Scholar or arXiv network calls.
- Real Obsidian MCP setup.
- Final demo screen recording.
- Bulk deletion or cleanup of pytest temp directories.

## File Structure

- Create: `app/research_workflow/tool_registry.py`
  - Tool registration, dispatch, validation, standardized result/error models, health reports, and JSONL call tracing.
- Create: `app/research_workflow/tool_adapters.py`
  - Zotero, Obsidian, Semantic Scholar, and arXiv adapter classes with local fallback health and minimal deterministic behavior.
- Create: `app/research_workflow/mcp_server.py`
  - ResearchAgent MCP-style tool facade for local tested capabilities.
- Create: `app/research_workflow/synthesis.py`
  - Deterministic synthesis generator for Milestone 4 Knowledge Pack files.
- Modify: `app/research_workflow/knowledge_pack.py`
  - Add synthesis artifact writing helpers and include generated artifacts in summary/trace.
- Modify: `app/research_workflow/service.py`
  - Route M2/M4 workflow operations through the tool registry and run synthesis/publishing steps after paper processing.
- Modify: `app/research_workflow/schemas.py`
  - Add generated artifact metadata fields if needed by synthesis or publishing.
- Modify: `app/routers/research_runs.py`
  - Add tool health endpoint and ResearchAgent tool-call endpoint.
- Modify: `ui/streamlit_app.py`
  - Add Tool Health display and run-result links/timeline visibility.
- Test: `tests/test_tool_registry.py`
  - Registry dispatch, validation, error normalization, health, fallback, and call trace tests.
- Test: `tests/test_tool_adapters.py`
  - Local fallback adapters for Zotero, Obsidian, Semantic Scholar, and arXiv.
- Test: `tests/test_research_agent_mcp_server.py`
  - At least five callable ResearchAgent tool facade operations.
- Test: `tests/test_research_run_service.py`
  - Registry trace integration and M4 synthesis/publishing workflow behavior.
- Test: `tests/test_synthesis.py`
  - Knowledge Pack generator output content and file shape.
- Test: `tests/test_research_run_router.py`
  - Tool health and tool-call API shapes.
- Test: `tests/test_research_workflow_ui_import.py`
  - UI source smoke checks for Tool Health, fallback status, generated outputs, and agent timeline labels.

## Shared Verification Commands

Use the project interpreter:

```powershell
& 'D:\Hcworkspace\Anoconda3\envs\research_agent\python.exe' -m pytest <paths> -q
```

Do not use `conda run` for verification in this Windows shell.

## Task 1: Add Tool Registry and Standardized Tool-Call Records

**Files:**

- Create: `app/research_workflow/tool_registry.py`
- Modify: `app/research_workflow/knowledge_pack.py`
- Test: `tests/test_tool_registry.py`
- Test: `tests/test_research_run_service.py`

- [ ] **Step 1: Write registry tests**

Create tests that cover:

- registering a tool named `research_agent.echo`;
- dispatching with required arguments;
- failed argument validation when a required key is missing;
- exception normalization into a failed result;
- `fallback_used` and `provider` fields;
- JSONL trace records containing `run_id`, `tool_name`, `provider`, `arguments`, `status`, `result_summary`, `error`, `started_at`, `completed_at`, `duration_ms`, and `fallback_used`.

- [ ] **Step 2: Run tests and verify they fail**

Run:

```powershell
& 'D:\Hcworkspace\Anoconda3\envs\research_agent\python.exe' -m pytest tests/test_tool_registry.py -q
```

Expected: FAIL because `app.research_workflow.tool_registry` does not exist.

- [ ] **Step 3: Implement registry**

Implement:

- `ToolCallResult`
- `ToolHealth`
- `ToolDefinition`
- `ToolRegistry.register()`
- `ToolRegistry.dispatch()`
- `ToolRegistry.health()`
- `ToolRegistry.call_records()`
- `build_default_tool_registry()`

Keep the API synchronous and deterministic. The registry should call `append_tool_call_record(run, record)` when a run is passed to dispatch.

- [ ] **Step 4: Run registry tests**

Run:

```powershell
& 'D:\Hcworkspace\Anoconda3\envs\research_agent\python.exe' -m pytest tests/test_tool_registry.py -q
```

Expected: PASS.

## Task 2: Add Local Fallback Tool Adapters

**Files:**

- Create: `app/research_workflow/tool_adapters.py`
- Test: `tests/test_tool_adapters.py`

- [ ] **Step 1: Write adapter tests**

Tests should cover:

- `ZoteroAdapter.health()` reports local HTTP fallback capability.
- `ObsidianAdapter.publish_markdown()` writes a Markdown file below an allowed vault root and returns the written path.
- `SemanticScholarAdapter.enrich()` returns a fallback record based on local paper metadata when unavailable.
- `ArxivAdapter.find_preprint()` returns a fallback record based on local paper metadata/PDF when unavailable.

- [ ] **Step 2: Run tests and verify they fail**

Run:

```powershell
& 'D:\Hcworkspace\Anoconda3\envs\research_agent\python.exe' -m pytest tests/test_tool_adapters.py -q
```

Expected: FAIL because `app.research_workflow.tool_adapters` does not exist.

- [ ] **Step 3: Implement adapters**

Implement local-first adapters with no live network dependency in tests. For direct Markdown writes, reject absolute destination names and parent traversal in logical note names.

- [ ] **Step 4: Run adapter tests**

Run:

```powershell
& 'D:\Hcworkspace\Anoconda3\envs\research_agent\python.exe' -m pytest tests/test_tool_adapters.py -q
```

Expected: PASS.

## Task 3: Add ResearchAgent MCP-Style Tool Facade

**Files:**

- Create: `app/research_workflow/mcp_server.py`
- Test: `tests/test_research_agent_mcp_server.py`

- [ ] **Step 1: Write MCP facade tests**

Tests should call at least five tools:

- `research_agent.list_papers`
- `research_agent.get_run_trace`
- `research_agent.export_knowledge_pack`
- `research_agent.search_chunks`
- `research_agent.answer_question`

Use temporary stores and fake vector/QA callbacks where needed. The request/response shape should include `tool_name`, `status`, `result`, and `error`.

- [ ] **Step 2: Run tests and verify they fail**

Run:

```powershell
& 'D:\Hcworkspace\Anoconda3\envs\research_agent\python.exe' -m pytest tests/test_research_agent_mcp_server.py -q
```

Expected: FAIL because `app.research_workflow.mcp_server` does not exist.

- [ ] **Step 3: Implement MCP facade**

Implement:

- `MCPToolRequest`
- `MCPToolResponse`
- `ResearchAgentMCPServer`
- `ResearchAgentMCPServer.call_tool()`
- `ResearchAgentMCPServer.tool_health()`

This is an in-process tested facade, not a live stdio server.

- [ ] **Step 4: Run MCP facade tests**

Run:

```powershell
& 'D:\Hcworkspace\Anoconda3\envs\research_agent\python.exe' -m pytest tests/test_research_agent_mcp_server.py -q
```

Expected: PASS with at least five callable tools.

## Task 4: Integrate Tool Registry with ResearchRun Service, Router, and UI Health

**Files:**

- Modify: `app/research_workflow/service.py`
- Modify: `app/routers/research_runs.py`
- Modify: `ui/streamlit_app.py`
- Test: `tests/test_research_run_service.py`
- Test: `tests/test_research_run_router.py`
- Test: `tests/test_research_workflow_ui_import.py`

- [ ] **Step 1: Add integration tests**

Tests should assert:

- a local research run records registry-shaped tool-call JSONL records;
- router exposes `GET /research-runs/tools/health`;
- router exposes `POST /research-runs/tools/call` for a safe facade tool;
- Streamlit source contains `Tool Health`, `fallback`, `ResearchAgent MCP Server`, `Semantic Scholar`, and `arXiv`.

- [ ] **Step 2: Run integration tests and verify they fail**

Run:

```powershell
& 'D:\Hcworkspace\Anoconda3\envs\research_agent\python.exe' -m pytest tests/test_research_run_service.py::test_research_run_service_execute_local_run_records_registry_tool_fields tests/test_research_run_router.py::test_research_run_tools_health_route tests/test_research_run_router.py::test_research_run_tool_call_route tests/test_research_workflow_ui_import.py::test_research_workflow_ui_contains_tool_health_status -q
```

Expected: FAIL until service/router/UI are wired.

- [ ] **Step 3: Wire service, router, and UI**

Use the registry for existing Zotero collection and paper processing records. Add router endpoints before `/{run_id}` routes so they are not shadowed. Add UI status display in the Research Workflow page without changing unrelated pages.

- [ ] **Step 4: Run integration tests**

Run:

```powershell
& 'D:\Hcworkspace\Anoconda3\envs\research_agent\python.exe' -m pytest tests/test_research_run_service.py tests/test_research_run_router.py tests/test_research_workflow_ui_import.py -q
```

Expected: PASS.

## Task 5: Add Deterministic Multi-Agent Synthesis

**Files:**

- Create: `app/research_workflow/synthesis.py`
- Modify: `app/research_workflow/schemas.py`
- Test: `tests/test_synthesis.py`

- [ ] **Step 1: Write synthesis tests**

Tests should build a run with two completed paper items and assert generated outputs include:

- `01 Literature Review.md`
- `02 Method Matrix.md`
- `03 Research Gaps.md`
- `04 Experiment Plan.md`
- `05 Reading Roadmap.md`

Tests should assert evidence links reference Zotero item ids and paper ids, and the experiment plan includes objective, dataset, baseline, metrics, and next actions.

- [ ] **Step 2: Run tests and verify they fail**

Run:

```powershell
& 'D:\Hcworkspace\Anoconda3\envs\research_agent\python.exe' -m pytest tests/test_synthesis.py -q
```

Expected: FAIL because `app.research_workflow.synthesis` does not exist.

- [ ] **Step 3: Implement synthesis generator**

Implement deterministic, no-LLM helpers:

- `KnowledgePackFile`
- `SynthesisResult`
- `KnowledgePackSynthesisService.generate(run)`

Use run paper metadata, paper ids, titles, creators, years, DOI/URL, and item artifacts. Skip failed/skipped papers but include a short limitations section.

- [ ] **Step 4: Run synthesis tests**

Run:

```powershell
& 'D:\Hcworkspace\Anoconda3\envs\research_agent\python.exe' -m pytest tests/test_synthesis.py -q
```

Expected: PASS.

## Task 6: Publish Complete Obsidian-Ready Knowledge Pack

**Files:**

- Modify: `app/research_workflow/knowledge_pack.py`
- Modify: `app/research_workflow/service.py`
- Test: `tests/test_research_run_service.py`
- Test: `tests/test_synthesis.py`

- [ ] **Step 1: Add publishing tests**

Tests should assert:

- `execute_local_run()` produces synthesis files after local paper processing succeeds;
- literature synthesis, experiment planning, and obsidian publishing steps become completed;
- generated artifact labels are attached to the run;
- summary and trace include generated artifact paths;
- `tool-calls.jsonl` includes synthesis and publishing tool records.

- [ ] **Step 2: Run publishing tests and verify they fail**

Run:

```powershell
& 'D:\Hcworkspace\Anoconda3\envs\research_agent\python.exe' -m pytest tests/test_research_run_service.py::test_research_run_service_execute_local_run_generates_knowledge_pack_outputs -q
```

Expected: FAIL until synthesis is wired into execution.

- [ ] **Step 3: Wire synthesis and direct publishing**

After paper understanding completes, run deterministic synthesis when there is at least one completed paper. Write files into the run output directory and attach artifacts. If `obsidian_publish` is true and `obsidian_vault_path` is set, also publish copies through `ObsidianAdapter`; otherwise mark direct run directory publishing as the fallback path.

- [ ] **Step 4: Run publishing tests**

Run:

```powershell
& 'D:\Hcworkspace\Anoconda3\envs\research_agent\python.exe' -m pytest tests/test_research_run_service.py tests/test_synthesis.py -q
```

Expected: PASS.

## Task 7: Add Run Result Page Signals and Agent Timeline

**Files:**

- Modify: `ui/streamlit_app.py`
- Test: `tests/test_research_workflow_ui_import.py`

- [ ] **Step 1: Add UI source tests**

Tests should assert UI source contains:

- `Agent Timeline`
- `Knowledge Pack Outputs`
- `Literature Review`
- `Method Matrix`
- `Research Gaps`
- `Experiment Plan`
- `Reading Roadmap`
- `tool-calls.jsonl`

- [ ] **Step 2: Run UI tests and verify they fail**

Run:

```powershell
& 'D:\Hcworkspace\Anoconda3\envs\research_agent\python.exe' -m pytest tests/test_research_workflow_ui_import.py::test_research_workflow_ui_contains_m4_result_signals -q
```

Expected: FAIL until UI source is updated.

- [ ] **Step 3: Update UI**

Add compact run-result sections in the existing Research Workflow page. Do not create a landing page or new unrelated page.

- [ ] **Step 4: Run UI tests**

Run:

```powershell
& 'D:\Hcworkspace\Anoconda3\envs\research_agent\python.exe' -m pytest tests/test_research_workflow_ui_import.py -q
```

Expected: PASS.

## Task 8: M3/M4 Verification and Execution Tracker

**Files:**

- Modify: `.codex/plans/current-plan.md`
- Modify: `.codex/tasks/current-tasks.md`
- Optional Modify: `docs/API_REFERENCE.md`
- Optional Modify: `docs/RUN_GUIDE.md`

- [ ] **Step 1: Run focused M3/M4 tests**

Run:

```powershell
& 'D:\Hcworkspace\Anoconda3\envs\research_agent\python.exe' -m pytest tests/test_tool_registry.py tests/test_tool_adapters.py tests/test_research_agent_mcp_server.py tests/test_synthesis.py tests/test_research_run_service.py tests/test_research_run_router.py tests/test_research_workflow_ui_import.py -q
```

Expected: PASS.

- [ ] **Step 2: Run M2 compatibility tests**

Run:

```powershell
& 'D:\Hcworkspace\Anoconda3\envs\research_agent\python.exe' -m pytest tests/test_zotero_intake.py tests/test_paper_processing_service.py tests/test_research_run_store.py -q
```

Expected: PASS.

- [ ] **Step 3: Inspect diff**

Run:

```powershell
git diff --stat
git diff --check
git status --short
```

Expected: no whitespace errors, no `.env` changes, no bulk deletions.

- [ ] **Step 4: Update tracker**

Mark completed tasks in `.codex/tasks/current-tasks.md` with result, files, tests, acceptance decision, and next step notes.

## Full M3/M4 Acceptance Check

Run:

```powershell
& 'D:\Hcworkspace\Anoconda3\envs\research_agent\python.exe' -m pytest tests/test_tool_registry.py tests/test_tool_adapters.py tests/test_research_agent_mcp_server.py tests/test_synthesis.py tests/test_research_run_service.py tests/test_research_run_router.py tests/test_research_workflow_ui_import.py tests/test_zotero_intake.py tests/test_paper_processing_service.py tests/test_research_run_store.py -q
```

Expected: PASS.

Then inspect:

```powershell
git diff --stat
git diff --check
git status --short
```

Expected:

- M3/M4 source, test, and tracker changes are visible.
- Unrelated local `.codex/`, pytest temp, and `third_party/` untracked items remain untouched.
- No recursive deletion command is needed or used.

## Self-Review Checklist

- M3 acceptance maps to Tasks 1-4.
- M4 acceptance maps to Tasks 5-7.
- Task 8 verifies the full implementation.
- External integrations remain fallback-friendly.
- The primary demo remains Zotero Collection -> Multi-Agent Review -> Obsidian Knowledge Pack.
- No `.env` edits.
- No bulk deletions.
