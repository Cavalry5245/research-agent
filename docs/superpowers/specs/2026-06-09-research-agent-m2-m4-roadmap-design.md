# ResearchAgent Milestone 2-4 Roadmap Design

## Purpose

This document plans the remaining ResearchAgent implementation after Milestone 1.

Milestone 1 already created the visible ResearchRun workflow skeleton: run schemas,
file persistence, local Knowledge Pack skeletons, FastAPI routes, and a Streamlit
launcher/monitor. The remaining work should turn that skeleton into a resume-grade
agent project:

```text
Zotero Collection -> Local Paper Processing -> MCP Hub -> Multi-Agent Synthesis -> Obsidian Knowledge Pack
```

Final screen-recording and video production are out of scope for Codex. The project
should still provide README content, architecture diagrams, and demo-script notes
that the user can use when recording independently.

## Guiding Strategy

Use a mixed route rather than a pure product-first or architecture-first route:

1. **Milestone 2:** make the workflow consume a real Zotero collection and produce
   per-paper outputs.
2. **Milestone 3:** MCP-enable the capabilities that now work locally.
3. **Milestone 4:** add multi-agent synthesis and publish a complete Knowledge Pack.

This keeps every stage runnable and demonstrable. Each milestone should leave the
project in a state that can be shown independently.

## Non-Goals

- Do not make arbitrary paper search the primary entry point.
- Do not make chat the central workflow.
- Do not require every external MCP integration to be live for the demo.
- Do not rewrite the existing PDF, RAG, note, comparison, or Zotero services unless
  the workflow integration exposes a concrete bug.
- Do not modify `.env` without explicit user approval.
- Do not include final screen recording as a Codex deliverable.

## Milestone 2: Zotero Collection to Local Paper Processing

### Goal

Make the ResearchRun workflow process real papers from a Zotero collection.

After Milestone 2, ResearchAgent should be able to take a Zotero collection with
three to five papers, resolve local PDFs, parse/index them, generate per-paper notes,
and record item-level success or failure without stopping the whole run.

### User Experience

The user opens the `Research Workflow` page, enters or selects a Zotero collection,
chooses a max paper count, and starts a run.

The Run Monitor shows:

- Run status and progress.
- Collection item status.
- Paper title, Zotero item id, resolved PDF path, synced paper id.
- Parse/index/note status for each item.
- Failure or skipped reason when an item cannot be processed.
- Knowledge Pack output paths.

### Core Data Model Additions

Add item-level workflow models:

- `ResearchRunPaperStatus`: `queued`, `running`, `completed`, `failed`, `skipped`.
- `ResearchRunPaperItem`:
  - `item_id`
  - `title`
  - `zotero_item_id`
  - `paper_id`
  - `pdf_path`
  - `metadata`
  - `status`
  - `progress`
  - `error`
  - `artifacts`
  - `created_at`, `updated_at`, `started_at`, `completed_at`

Update `ResearchRun` to include `paper_items`.

### Workflow Components

Add a `CollectionIntakeService` under `app/research_workflow/` that coordinates:

- Zotero collection item listing.
- Metadata normalization.
- PDF path resolution.
- Item selection and max-paper limiting.

Add a `PaperProcessingService` under `app/research_workflow/` that coordinates:

- Syncing PDFs into ResearchAgent storage.
- Parsing PDFs through the existing parser service.
- Chunking and indexing through existing RAG services.
- Per-paper note generation through the existing note generator.
- Writing per-paper Markdown files into the run Knowledge Pack.

The services should reuse existing app services instead of duplicating PDF, chunking,
embedding, vector store, or note-generation logic.

### Trace and Artifact Behavior

Update `trace.json` and `tool-calls.jsonl` incrementally during the run.

Trace should include:

- Collection input.
- Each Zotero item considered.
- Each paper item status transition.
- PDF resolution result.
- Parse/index/note outcomes.
- Error and fallback events.

Knowledge Pack should contain:

- Updated `00 Run Summary.md`.
- One Markdown note per successful paper under `papers/`.
- Trace artifacts under `assets/`.

### Failure Handling

Item failures must not stop the whole run.

Examples:

- Missing PDF: mark item `skipped` or `failed` with reason.
- Duplicate paper: mark item `skipped` and link existing `paper_id` when possible.
- Parse failure: mark item `failed`, keep processing remaining items.
- Note-generation failure: mark item `failed` or `completed_with_missing_note` only if
  a more granular status is added later.

### Testing

Tests should cover:

- Collection item normalization.
- PDF path resolution success and missing PDF.
- Per-item failure does not stop the run.
- Store persistence for `paper_items`.
- Knowledge Pack paper-note file creation.
- Trace file updates.
- API and Streamlit smoke behavior with fake Zotero clients.

### Acceptance Criteria

- A real or fake Zotero collection with three to five items can be processed.
- Each successful paper has a stored `paper_id` and paper note.
- Failed or skipped papers are visible and traceable.
- The run summary reports processed, failed, and skipped counts.
- No external Semantic Scholar, arXiv, Obsidian, or MCP dependency is required.

## Milestone 3: MCP Hub and ResearchAgent MCP Server

### Goal

Make MCP a real architectural capability, not just a label.

After Milestone 3, ResearchAgent should expose its own capabilities through an MCP
server and route workflow tool calls through a registry that can use local fallback
adapters when external MCP servers are unavailable.

### Tool Registry

Add a tool registry under `app/tools/` or `app/research_workflow/tools/`.

Responsibilities:

- Register tool definitions.
- Validate arguments.
- Normalize return values.
- Normalize errors.
- Record each tool call into `tool-calls.jsonl`.
- Report tool health and fallback status.

Tool call record fields:

- `run_id`
- `tool_name`
- `provider`
- `arguments`
- `status`
- `result_summary`
- `error`
- `started_at`
- `completed_at`
- `duration_ms`
- `fallback_used`

### ResearchAgent MCP Server

Add a ResearchAgent MCP Server that exposes tested local capabilities:

- `research_agent.list_papers`
- `research_agent.parse_paper`
- `research_agent.index_paper`
- `research_agent.generate_paper_note`
- `research_agent.search_chunks`
- `research_agent.answer_question`
- `research_agent.compare_papers`
- `research_agent.get_run_trace`
- `research_agent.export_knowledge_pack`

Keep the first version conservative. Expose tools that already work locally before
adding complex synthesis tools.

### External Tool Adapters

Add adapters with fallback behavior:

- Zotero adapter:
  - Prefer existing Zotero MCP/local API path.
  - Fallback to direct local Zotero database/PDF path resolution where already
    supported.
- Obsidian adapter:
  - Prefer Obsidian MCP if configured.
  - Fallback to direct Markdown writes into `obsidian_vault_path`.
- Semantic Scholar adapter:
  - Enrich metadata, citations, references, and related papers.
  - Fallback to local Zotero metadata when unavailable.
- arXiv adapter:
  - Find preprints or open PDFs by title.
  - Fallback to local Zotero PDF only.

### UI Additions

Add a `Tool Settings` or `Tool Health` section to Streamlit.

It should show:

- Zotero status.
- ResearchAgent MCP Server status.
- Obsidian status.
- Semantic Scholar status.
- arXiv status.
- Active fallback mode.

### Testing

Tests should cover:

- Tool registry registration and dispatch.
- Error normalization.
- Tool-call trace writing.
- ResearchAgent MCP tool request/response shape.
- Adapter fallback when an external tool is unavailable.
- UI source/smoke test for tool status display.

### Acceptance Criteria

- At least five ResearchAgent MCP tools are callable in tests.
- The run trace includes standardized tool-call records.
- UI shows tool connection status and fallback status.
- Zotero and Obsidian each have a verified adapter or fallback path.
- Core collection processing still works when a noncritical external adapter is unavailable.

## Milestone 4: Multi-Agent Synthesis and Obsidian Knowledge Pack

### Goal

Complete the final product demo: a Zotero collection produces a multi-page
Obsidian-ready Knowledge Pack with evidence-backed synthesis and an actionable
experiment plan.

### Agent Architecture

Implement five specialist agents:

- `CollectionIntakeAgent`
  - Uses Milestone 2 intake and status tracking.
- `PaperUnderstandingAgent`
  - Produces structured paper summaries from parsed content and retrieved chunks.
- `LiteratureSynthesisAgent`
  - Produces literature review, method matrix, and research gaps.
- `ExperimentPlanningAgent`
  - Produces experiment hypothesis, baselines, metrics, ablations, risks, and schedule.
- `ObsidianPublishingAgent`
  - Publishes or writes the final Knowledge Pack and records artifact links.

Agents should operate on structured inputs and outputs. Markdown rendering should
happen after structured JSON is produced.

### Structured Outputs

Add schemas for:

- `PaperUnderstandingResult`
- `LiteratureReviewResult`
- `MethodMatrixResult`
- `ResearchGapResult`
- `ExperimentPlanResult`
- `ReadingRoadmapResult`

Each major claim should include evidence references when possible:

- `paper_id`
- `zotero_item_id`
- `chunk_id`
- `section`
- `artifact_path`

### Knowledge Pack Outputs

Each completed run should produce:

- `00 Run Summary.md`
- `01 Literature Review.md`
- `02 Method Matrix.md`
- `03 Research Gaps.md`
- `04 Experiment Plan.md`
- `05 Reading Roadmap.md`
- `papers/*.md`
- `assets/trace.json`
- `assets/tool-calls.jsonl`
- `assets/eval-summary.md`

### Quality and Anti-Hallucination Rules

Generation prompts must require:

- Chinese academic tone unless the user selects otherwise.
- No unsupported claims.
- Use "原文未明确说明" when evidence is missing.
- Evidence links for key claims.
- Clear distinction between observed paper evidence and inferred recommendations.

Add lightweight evaluators:

- Missing evidence detector.
- Empty-section detector.
- Markdown artifact completeness check.
- Retrieval evidence summary.

### UI Additions

Upgrade the Research Workflow page with:

- Agent timeline.
- Tool-call/fallback summaries.
- Artifact links.
- Knowledge Pack preview.
- Result status and failure explanation.

Do not make chat the primary interface. Chat can link into existing agent tools as a
secondary experience.

### Obsidian Publishing

If Obsidian MCP is available:

- Create folders.
- Create or update notes.
- Return Obsidian paths.

If unavailable:

- Write Markdown directly to the configured vault path.
- Mark fallback in trace and UI.

### Testing

Tests should cover:

- Structured output schemas.
- Markdown rendering from structured outputs.
- Evidence references included in generated sections.
- Knowledge Pack completeness.
- Obsidian MCP fallback.
- Agent timeline status transitions.
- End-to-end fake run with three papers.

### Acceptance Criteria

- One Zotero collection produces a complete Knowledge Pack.
- Literature Review includes taxonomy, trends, unresolved problems, and evidence.
- Method Matrix links rows to papers or chunks.
- Research Gaps are actionable and evidence-backed.
- Experiment Plan includes baselines, datasets, metrics, ablations, risks, and schedule.
- UI shows a clear agent timeline and artifact links.
- README/demo-script material explains how the user can record the workflow, but
  Codex does not produce the final recording.

## Cross-Milestone Documentation

Add or update these docs as the milestones land:

- README feature summary.
- Architecture diagram.
- MCP tool reference.
- Demo script notes.
- Resume bullet wording.

The demo script should describe a three-to-five-minute flow, but recording and
editing the video remains the user's task.

## Recommended Implementation Plan Order

1. Milestone 2 implementation plan.
2. Milestone 2 implementation and verification.
3. Milestone 3 implementation plan.
4. Milestone 3 implementation and verification.
5. Milestone 4 implementation plan.
6. Milestone 4 implementation and verification.
7. Documentation and resume packaging.

Each milestone should have its own detailed implementation plan with task-level file
ownership, verification commands, and review checkpoints.

## Risks and Fallbacks

- Zotero item data may be incomplete.
  - Fallback: process available metadata and mark missing fields.
- PDFs may be missing or duplicated.
  - Fallback: skip or link existing paper ids, continue the run.
- External MCP servers may be unavailable.
  - Fallback: local adapters and direct Markdown writes.
- Long runs may fail halfway.
  - Fallback: item-level statuses, persistent run store, resumable future design.
- Generated synthesis may hallucinate.
  - Fallback: structured outputs, evidence references, and evaluators.
- File-backed store may face multi-process write contention.
  - Fallback: process-local locking for current app, future hardening with SQLite or
    a cross-process lock if needed.

## Approval Gate

This roadmap is ready for user review. Once approved, the next step is to use
`superpowers:writing-plans` to create the Milestone 2 implementation plan.
