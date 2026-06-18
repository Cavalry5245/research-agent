# ResearchAgent React Frontend Replacement Design

Date: 2026-06-18
Status: Approved design brief, pending implementation plan

## Goal

Replace the Streamlit UI with a modern React workspace while keeping the existing FastAPI backend and service layer. The React app should become the primary user interface once it reaches functional parity, while Streamlit remains available during migration as a legacy/debug entry.

The product direction is a hybrid of:

- Developer console: clear task state, MCP Hub health, Agent Timeline, traces, logs, and operational feedback.
- Paper knowledge product: strong paper library, note, QA, comparison, citation/source, and research workflow experiences.

## Non-Goals

- Do not remove Streamlit during the first React implementation.
- Do not rewrite the Python service layer.
- Do not build a marketing landing page.
- Do not rely on static mock data for core flows once API endpoints exist.
- Do not batch-delete old UI files or generated files.

## Current UI Surface

The existing Streamlit app exposes these user-facing areas:

- Research Workflow: Zotero collection intake, MCP Hub status, research runs, Agent Timeline, paper items, Knowledge Pack outputs.
- Paper Upload: multi-PDF upload, save, parse, index, delete, and paper list.
- Notes: select paper, reparse, generate Markdown note, preview, download.
- QA: whole-library or single-paper question answering with source chunks.
- Compare: 2-5 paper comparison and Markdown preview/download.
- Knowledge Base: manual paper indexing and vector-store status.
- Agent Assistant: free chat, full paper analysis workflow, multi-paper comparison workflow.
- Agent Monitor: execution timeline, routing decisions, tool statistics.

## Target Information Architecture

React routes should be designed around product workflows rather than directly copying Streamlit tabs.

```text
/dashboard
/workflow
/papers
/papers/:paperId
/notes
/qa
/compare
/knowledge-base
/agent
/monitor
/settings
```

### Route Responsibilities

`/dashboard`

- Show system health, LLM/embedding/vector status, MCP Hub summary, recent jobs, recent papers, and recent research runs.
- Give fast access to upload, start workflow, ask question, and inspect failed jobs.

`/workflow`

- Replace the Streamlit Research Workflow tab.
- Load Zotero collections, allow manual collection fallback, create research runs, execute local runs, show Agent Timeline, paper items, artifacts, and Knowledge Pack outputs.
- Surface MCP Hub status honestly, including fallback-active states.

`/papers`

- Replace upload and paper-library management.
- Support drag-and-drop upload, batch save, parse, index, index status, delete confirmation, and paper search/filter.

`/papers/:paperId`

- Show parsed metadata, source PDF path/download, note status, index status, sections, source chunks, and paper-scoped actions.
- Provide a paper-scoped QA launcher.

`/notes`

- Select paper, generate note, show job status, preview Markdown, and download the generated note.

`/qa`

- Support whole-library and single-paper QA.
- Show answer, source chunks, paper IDs, section labels, and retrieval metadata when available.

`/compare`

- Select 2-5 papers, submit synchronous or background comparison, preview Markdown result, and download output.

`/knowledge-base`

- List knowledge bases, create a knowledge base, add/remove papers, and inspect vector-store/library status.

`/agent`

- Provide free conversation with supervisor/react modes.
- Support dedicated workflow launchers for full paper analysis and multi-paper comparison once API endpoints exist.

`/monitor`

- Replace Agent Monitor with traces, routing decisions, tool statistics, latency, and filterable events.

`/settings`

- Show local runtime configuration status, model configuration, Zotero Local API status, Obsidian status, and backend connection status.

## Visual And Interaction Model

The UI should be dense, calm, and operational:

- Left sidebar for stable navigation.
- Top bar for backend connection, model status, and current workspace context.
- Main content area for tables, forms, and workflow panels.
- Right detail drawer or route-level detail panel for Agent Timeline, source chunks, artifacts, and logs.
- Use compact tables for papers, jobs, traces, and runs.
- Use clear status tokens for queued, running, completed, failed, cancelled, unavailable, fallback active, and degraded.
- Use icons for actions and status where familiar, with accessible labels/tooltips.
- Avoid a landing-page hero, decorative gradients, and oversized marketing layout.

## Frontend Stack

```text
Vite
React
TypeScript
React Router
TanStack Query
Zustand
Tailwind CSS
shadcn/ui + Radix UI
Lucide Icons
Vitest + Testing Library
Playwright
```

### State Model

- Use TanStack Query for server state: papers, tasks, research runs, traces, health, knowledge bases.
- Use Zustand only for UI-local global state: selected workspace context, sidebar state, active detail drawer, user preferences.
- Keep form state inside route components or colocated hooks.
- Avoid duplicating server state in Zustand.

## Proposed Frontend Structure

```text
frontend/
  package.json
  vite.config.ts
  tsconfig.json
  src/
    app/
      App.tsx
      router.tsx
      queryClient.ts
      providers.tsx
    api/
      client.ts
      health.ts
      papers.ts
      tasks.ts
      researchRuns.ts
      zotero.ts
      qa.ts
      compare.ts
      agent.ts
      traces.ts
      knowledgeBase.ts
      system.ts
    components/
      layout/
      status/
      tables/
      markdown/
      upload/
      timeline/
      empty-state/
      error-state/
    pages/
      dashboard/
      workflow/
      papers/
      paper-detail/
      notes/
      qa/
      compare/
      knowledge-base/
      agent/
      monitor/
      settings/
    stores/
      uiStore.ts
    test/
      setup.ts
```

## Existing API Coverage

The current FastAPI app already covers much of the replacement surface:

- `GET /health`
- `GET /papers`
- `POST /papers/upload`
- `POST /papers/{paper_id}/parse`
- `POST /papers/{paper_id}/index`
- `GET /papers/{paper_id}/index-status`
- `GET /library/index-status`
- `DELETE /papers/{paper_id}`
- `POST /tasks/note/{paper_id}`
- `POST /tasks/compare`
- `GET /tasks`
- `GET /tasks/{job_id}`
- `GET /tasks/{job_id}/result`
- `DELETE /tasks/{job_id}`
- `POST /tasks/{job_id}/retry`
- `POST /qa`
- `POST /papers/compare`
- `POST /agent/execute`
- `GET /api/traces`
- `GET /api/traces/stats`
- `POST /research-runs`
- `GET /research-runs`
- `GET /research-runs/tools/health`
- `POST /research-runs/{run_id}/execute-local`
- `GET /research-runs/{run_id}`
- `DELETE /research-runs/{run_id}`
- `GET /kb`
- `POST /kb`
- `POST /kb/{kb_id}/papers`
- `DELETE /kb/{kb_id}/papers/{paper_id}`

## API Gaps For Full Replacement

React cannot directly call Python services the way Streamlit does. Add narrow FastAPI endpoints for the remaining UI-only service calls.

### Required

```text
GET  /zotero/collections
POST /papers/upload-batch
POST /papers/parse-and-index-batch
GET  /system/status
```

`GET /zotero/collections`

- Wrap `ZoteroLocalHttpClient.list_collections`.
- Return collection key, name, parent collection, and item count.
- Preserve manual collection entry as a UI fallback when Zotero is unavailable.

`POST /papers/upload-batch`

- Accept multiple PDFs in one request.
- Return saved file records with generated paper IDs.
- Keep per-file errors instead of failing the entire batch when possible.

`POST /papers/parse-and-index-batch`

- Accept saved upload records or paper IDs.
- Parse and index in one operation or submit a background task per paper.
- Return per-paper parse/index status, chunk count, and error.

`GET /system/status`

- Aggregate health, LLM configured, embedding model/device, vector store metadata, Zotero reachability, Obsidian config, and MCP Hub summary.
- Feed dashboard and top-bar status.

### Useful After Parity

```text
POST /agent/workflows/research
POST /agent/workflows/compare
GET  /events/stream
```

Workflow endpoints should replace Streamlit-only direct calls to LangGraph workflow builders. `GET /events/stream` can later provide SSE updates for tasks, traces, and research runs.

## Implementation Slices

### Slice 1: App Shell And API Foundation

- Create `frontend/` Vite React TypeScript app.
- Add router, layout, theme, sidebar, top status bar, TanStack Query setup, API client, and error handling.
- Implement `/dashboard` against `GET /health`, `GET /library/index-status`, `GET /tasks`, `GET /papers`, and `GET /research-runs/tools/health`.

### Slice 2: Papers

- Implement `/papers` and `/papers/:paperId`.
- Add batch upload endpoint if needed before UI wiring.
- Support upload, parse, index, delete confirmation, index status, and download links.

### Slice 3: Research Workflow

- Add Zotero collections endpoint.
- Implement `/workflow` with collection picker, manual fallback, run creation, local execution, run selector, Agent Timeline, paper items, Knowledge Pack outputs, artifacts, and MCP Hub.

### Slice 4: Notes, QA, Compare

- Implement `/notes`, `/qa`, and `/compare`.
- Prefer background tasks for long note/compare operations.
- Render Markdown outputs with safe Markdown handling.

### Slice 5: Knowledge Base, Agent, Monitor

- Implement `/knowledge-base`, `/agent`, and `/monitor`.
- Replace Streamlit Agent Monitor with API-backed trace tables and charts.
- Keep Agent chat mode parity with `/agent/execute`.

### Slice 6: Runtime Integration And Docs

- Add frontend dev/start scripts.
- Document two-service local development.
- Optionally mount the built React app from FastAPI for single-port local usage.
- Update README/RUN_GUIDE only after React reaches parity.

## Testing Strategy

### Unit And Component Tests

- API client request/response mapping.
- Query hooks for success, loading, empty, and error states.
- Form validation for collection, upload, QA, compare, and KB flows.
- Status badge and timeline rendering.

### End-To-End Tests

Use Playwright for:

- App loads and shows backend connection state.
- Papers page shows paper list and handles empty state.
- Upload flow can select files and display pending upload state.
- Research Workflow can show MCP Hub status and existing runs.
- QA submits a question and renders source chunks with mocked backend.
- Agent Monitor renders traces and tool statistics.

### Accessibility Checks

- Keyboard navigation through sidebar, tables, forms, dialogs, and drawers.
- Label all inputs and icon buttons.
- Use visible focus states.
- Ensure status is not color-only.
- Respect reduced-motion preferences for loading and timeline transitions.

## Migration Policy

- Streamlit remains available until React covers all critical flows.
- React becomes the documented primary entry after `/workflow`, `/papers`, `/qa`, `/compare`, `/agent`, and `/monitor` are usable.
- Do not delete Streamlit or docs in the migration PR.
- Keep changes narrow and staged; this repository currently has unrelated dirty/deleted files, so each implementation slice should touch only its intended files.

## Open Questions For Implementation Planning

- Should the React app be served only as a separate dev server first, or should FastAPI static mounting be included in Slice 1?
- Should long-running batch parse/index use one aggregate task or one task per paper?
- Should Agent workflow uploads be supported in the first Agent slice, or should they wait until after paper upload parity?
- Should the first visual pass use default shadcn styling or generate three visual variants before coding?

## Acceptance Criteria

- React app has a stable, typed API client and route structure for all Streamlit replacement areas.
- At least one end-to-end path reaches real backend data in each implemented slice.
- Missing backend capabilities are added as narrow FastAPI endpoints, not direct frontend service calls.
- UI includes loading, empty, error, and success states for every route.
- New frontend work does not remove or break the Streamlit entry during migration.
- Documentation clearly explains how to run the React frontend and FastAPI backend together.
