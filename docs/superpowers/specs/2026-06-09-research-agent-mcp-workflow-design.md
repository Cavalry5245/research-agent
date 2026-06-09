# ResearchAgent MCP Workflow Design

## Purpose

ResearchAgent will be repositioned from a collection of paper-reading features into a resume-grade AI Agent application:

**ResearchAgent: an MCP-driven multi-agent research workflow system that turns a Zotero collection into an Obsidian research knowledge pack.**

The target job signal is large-language-model and Agent application development. The project should demonstrate tool orchestration, MCP integration, RAG, structured generation, observability, and realistic research workflow automation.

## Product Narrative

The primary demo starts from a real Zotero collection. A user selects a collection, starts a research run, and the system coordinates multiple agents to:

1. Read the collection and paper metadata.
2. Resolve local PDFs or enrich missing metadata through external scholarly tools.
3. Parse, index, and summarize each paper.
4. Synthesize a multi-paper literature review.
5. Identify research gaps.
6. Generate an actionable experiment plan.
7. Publish the final knowledge pack into Obsidian.
8. Record a full execution trace and tool-call log.

The final demo should feel like a complete research automation workflow, not a general ChatPDF clone.

## Goals

- Provide one clear end-to-end demo: **Zotero Collection -> Multi-Agent Review -> Obsidian Knowledge Pack**.
- Implement a ResearchAgent MCP Server that exposes project capabilities as reusable MCP tools.
- Integrate external MCP/tool adapters for Zotero, Obsidian, Semantic Scholar, and arXiv.
- Preserve graceful fallback paths so the demo can run even if an external MCP server is unavailable.
- Generate concrete deliverables: literature review, method matrix, research gaps, experiment plan, reading roadmap, paper notes, trace artifacts.
- Make Agent execution observable: every run has a timeline, tool calls, errors, fallbacks, output paths, and status.

## Non-Goals

- Do not build a multi-user SaaS product.
- Do not prioritize arbitrary paper search as the main entry point; Zotero collection is the primary input.
- Do not make Agent chat the central experience. Chat can remain as a secondary interface.
- Do not depend on all external MCP integrations being live for the core demo.
- Do not rewrite the whole existing application before the main workflow is usable.

## Main Workflow

### User Flow

1. User opens ResearchAgent.
2. User selects a Zotero collection.
3. User chooses workflow options:
   - Semantic Scholar enrichment on or off.
   - arXiv PDF fallback on or off.
   - Obsidian publishing target.
   - Number of papers to process.
4. User starts a research run.
5. The Run Monitor shows agent steps, tool calls, and current status.
6. When complete, the Knowledge Pack page links to generated Obsidian notes and local trace artifacts.

### Agent Flow

```text
Zotero Collection
  -> CollectionIntakeAgent
  -> PaperUnderstandingAgent
  -> LiteratureSynthesisAgent
  -> ExperimentPlanningAgent
  -> ObsidianPublishingAgent
  -> Knowledge Pack
```

## System Modules

### Frontend Workbench

The existing Streamlit UI should be refocused around the research workflow.

Primary pages:

- **Workflow Launcher**: choose Zotero collection, configure tool options, start a run.
- **Run Monitor**: show agent timeline, tool status, failures, fallback use, output links.
- **Knowledge Pack**: preview generated review, method matrix, gaps, plan, and paper notes.
- **Tool Settings**: show MCP connection status for Zotero, ResearchAgent, Obsidian, Semantic Scholar, and arXiv.

Existing upload, QA, comparison, Zotero, and Agent tabs can remain as advanced or secondary tools, but the first screen should make the workflow obvious.

### Multi-Agent Orchestrator

The orchestrator creates and executes a `ResearchRun`.

Specialist agents:

- `CollectionIntakeAgent`: reads Zotero collection items, resolves metadata and PDFs.
- `PaperUnderstandingAgent`: parses, chunks, indexes, and summarizes each paper.
- `LiteratureSynthesisAgent`: creates literature review, method matrix, and research gaps.
- `ExperimentPlanningAgent`: creates baseline, ablation, risk, and schedule recommendations.
- `ObsidianPublishingAgent`: writes the knowledge pack into Obsidian and records output paths.

Agents should produce structured JSON first, then render Markdown. This keeps outputs testable and easier to inspect.

### Tool and MCP Layer

All tool calls go through a tool registry. The registry is responsible for:

- MCP server availability checks.
- Argument validation.
- Error normalization.
- Fallback selection.
- Tool-call tracing.
- Return value normalization.

Each specialist agent receives only the tools it needs.

### ResearchAgent Core Services

Existing capabilities to reuse:

- PDF parsing.
- Chunking.
- Embedding.
- Vector store.
- Hybrid retrieval.
- Cross-encoder reranking.
- Paper QA.
- Paper comparison.
- Note generation.
- Zotero local PDF path resolution.

Capabilities to add or strengthen:

- Structured paper summary.
- Literature review generator.
- Method matrix generator.
- Research gap identifier.
- Experiment plan generator.
- Knowledge pack exporter.
- Research run store and run status model.

### Observability

Every workflow execution has a `run_id`.

The system records:

- Run inputs.
- Step statuses.
- Agent decisions.
- MCP/tool calls.
- Tool arguments and normalized outputs.
- Durations.
- Errors.
- Fallback events.
- Generated artifact paths.

This should be visible in the UI and exported into the knowledge pack assets.

## MCP Tool Design

### Zotero Tools

Purpose: primary input layer for real user literature collections.

Tools:

- `zotero.list_collections`
- `zotero.list_collection_items`
- `zotero.get_item_metadata`
- `zotero.get_item_pdf`
- `zotero.create_note`

### Semantic Scholar Tools

Purpose: enrich scholarly context and help the synthesis agent reason about importance.

Tools:

- `semantic_scholar.search_papers`
- `semantic_scholar.get_paper`
- `semantic_scholar.get_citations`
- `semantic_scholar.get_references`
- `semantic_scholar.rank_related_papers`

### arXiv Tools

Purpose: find open PDFs and recent preprints when Zotero metadata or attachments are incomplete.

Tools:

- `arxiv.search`
- `arxiv.get_paper`
- `arxiv.download_pdf`
- `arxiv.find_by_title`

### Obsidian Tools

Purpose: publish the final research knowledge pack.

Tools:

- `obsidian.create_note`
- `obsidian.update_note`
- `obsidian.search_notes`
- `obsidian.create_folder`
- `obsidian.open_note`
- `obsidian.append_to_daily_note`

If Obsidian MCP is unavailable, fallback to direct Markdown file writes into the configured vault path.

### ResearchAgent MCP Server Tools

Purpose: expose the project itself as an MCP server so external Agent clients can reuse ResearchAgent capabilities.

Tools:

- `research_agent.list_papers`
- `research_agent.sync_zotero_item`
- `research_agent.parse_paper`
- `research_agent.index_paper`
- `research_agent.generate_paper_note`
- `research_agent.search_chunks`
- `research_agent.answer_question`
- `research_agent.compare_papers`
- `research_agent.generate_literature_review`
- `research_agent.generate_method_matrix`
- `research_agent.identify_research_gaps`
- `research_agent.generate_experiment_plan`
- `research_agent.export_knowledge_pack`
- `research_agent.get_run_trace`
- `research_agent.get_eval_summary`

## Knowledge Pack Deliverable

Each run creates an independent Obsidian-ready package:

```text
ResearchAgent/
  Runs/
    2026-06-09-IRSTD-literature-review/
      00 Run Summary.md
      01 Literature Review.md
      02 Method Matrix.md
      03 Research Gaps.md
      04 Experiment Plan.md
      05 Reading Roadmap.md
      papers/
        paper_001 - example.md
        paper_002 - example.md
      assets/
        trace.json
        tool-calls.jsonl
        eval-summary.md
```

### 00 Run Summary

Entry page for the knowledge pack.

Contains:

- Goal.
- Zotero collection.
- Papers processed.
- Success, failure, and skipped counts.
- MCP tools used.
- Key conclusions.
- Links to generated outputs.
- Trace artifact links.

### 01 Literature Review

Main synthesis output.

Contains:

- Research background.
- Task definition.
- Method taxonomy.
- Representative paper groups.
- Technical trends.
- Unresolved problems.
- Evidence-backed conclusions.

### 02 Method Matrix

Structured comparison table.

Columns:

- Paper.
- Task.
- Core method.
- Backbone or architecture.
- Dataset.
- Metrics.
- Strength.
- Limitation.
- Evidence.

Rows link to individual paper notes.

### 03 Research Gaps

Identifies actionable research opportunities.

Contains:

- Shared bottlenecks.
- Dataset and metric issues.
- Reproducibility risks.
- Low-cost research opportunities.
- High-risk high-reward directions.
- Evidence links.

### 04 Experiment Plan

Actionable plan for follow-up research.

Contains:

- Research hypothesis.
- Baselines.
- Datasets.
- Metrics.
- Experiment groups.
- Ablations.
- Expected outcomes.
- Risks and fallbacks.
- One-week, two-week, and four-week execution roadmap.

### 05 Reading Roadmap

Prioritized follow-up reading plan.

Contains:

- Must-read papers.
- Skim-only papers.
- Questions to answer while reading.
- Papers to reproduce or inspect more deeply.

### Paper Notes

Each paper note includes:

- Frontmatter.
- Why it matters.
- Problem.
- Method.
- Experiments.
- Key results.
- Limitations.
- Useful evidence.
- Zotero, PDF, Semantic Scholar, and arXiv links when available.

### Assets

- `trace.json`: structured run timeline.
- `tool-calls.jsonl`: MCP/tool call log.
- `eval-summary.md`: quality checks and retrieval evidence summary.

## Milestones

### Milestone 1: Research Workflow Run Skeleton

Goal: make the new product spine visible.

Build:

- `ResearchRun` model.
- Run store.
- Workflow launcher.
- Run monitor.
- Knowledge pack folder creation.
- Trace skeleton.

Acceptance:

- A run can be created without LLM calls.
- UI shows run status and output paths.
- A basic `00 Run Summary.md` is generated.

### Milestone 2: Zotero Collection to Local Paper Processing

Goal: make the real research input path work.

Build:

- Zotero collection listing.
- Collection item reading.
- PDF path resolution.
- Sync to ResearchAgent storage.
- Parse, chunk, index.
- Per-paper note generation.
- Paper-level status tracking.

Acceptance:

- A Zotero collection with three to five papers can be processed.
- Each successful paper has a paper note.
- Failed papers do not stop the whole run.
- Trace records item-level status.

### Milestone 3: MCP Hub and ResearchAgent MCP Server

Goal: make MCP a real architectural capability.

Build:

- ResearchAgent MCP Server.
- ResearchAgent MCP tools.
- Tool registry.
- Zotero, Obsidian, Semantic Scholar, and arXiv adapters.
- Tool status UI.
- Fallback behavior.

Acceptance:

- ResearchAgent tools can be called through MCP.
- UI shows tool connection status.
- Agent run trace includes MCP tool calls.
- Core demo still runs when a noncritical external MCP is unavailable.

### Milestone 4: Multi-Agent Synthesis and Obsidian Knowledge Pack

Goal: complete the final demo.

Build:

- Five specialist agents.
- Literature review generator.
- Method matrix generator.
- Research gap generator.
- Experiment plan generator.
- Reading roadmap generator.
- Obsidian publishing.
- Run result page.

Acceptance:

- One Zotero collection produces a complete Obsidian Knowledge Pack.
- Outputs include evidence links.
- Experiment plan is actionable.
- UI shows a clear agent timeline.
- Workflow can be recorded as a three-to-five-minute demo.

## Implementation Priority

Recommended order:

1. Research run model and workflow spine.
2. Zotero collection processing.
3. Knowledge pack generation.
4. ResearchAgent MCP Server.
5. External MCP adapters.
6. Multi-agent orchestration polish.
7. README, demo script, architecture diagram, and resume wording.

Even with the technology-highlight direction, the core demo must stay anchored on the Zotero-to-Obsidian workflow.

## Risks and Fallbacks

- External MCP servers may be unavailable or inconsistent.
  - Fallback: local adapters and cached metadata.
- Obsidian MCP setup may be tedious.
  - Fallback: direct Markdown writes to a configured vault path.
- Semantic Scholar or arXiv may not match every Zotero paper.
  - Fallback: title-only metadata and local PDF parsing.
- Long runs may fail midway.
  - Fallback: item-level status tracking and resumable runs.
- Generated synthesis may hallucinate.
  - Fallback: require evidence links from paper notes or retrieved chunks for key claims.

## Resume Positioning

Suggested project description:

> Built ResearchAgent, an MCP-driven multi-agent research workflow system that transforms a Zotero collection into an Obsidian knowledge pack. The system coordinates specialist agents for collection intake, paper understanding, literature synthesis, experiment planning, and publishing. It exposes parsing, RAG retrieval, comparison, synthesis, planning, and trace inspection through a custom ResearchAgent MCP Server, integrates Zotero, Semantic Scholar, arXiv, and Obsidian tool adapters, and records full tool-call traces for observability and debugging.

Technical keywords:

- MCP
- Multi-Agent orchestration
- Tool calling
- RAG
- Hybrid retrieval
- Cross-encoder reranking
- Zotero integration
- Obsidian knowledge management
- Semantic Scholar and arXiv enrichment
- FastAPI
- Streamlit
- Observability
- Structured generation

## Approval Gate

This design should be reviewed before implementation planning. After approval, the next step is to create an implementation plan with task-level sequencing, file ownership, verification commands, and staged acceptance checks.
