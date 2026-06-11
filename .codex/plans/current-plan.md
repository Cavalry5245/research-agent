# Milestone 3-4: MCP Hub and Obsidian Knowledge Pack

## Scope

Execute the implementation plan in:

`docs/superpowers/plans/2026-06-11-mcp-synthesis-knowledge-pack.md`

Goal: complete M3 and M4 by adding a local MCP-style tool hub, ResearchAgent tool facade, fallback adapters, deterministic multi-agent synthesis, Obsidian-ready Knowledge Pack publishing, and UI health/result visibility.

## Constraints

- Do not modify `.env` without explicit user approval.
- Do not bulk delete files or directories.
- Do not use `del /s`, `rd /s`, `rmdir /s`, `Remove-Item -Recurse`, or `rm -rf`.
- If deletion is necessary, delete only one explicit file path at a time.
- Do not delete datasets, checkpoints, outputs, logs, or experiment results.
- Work one task at a time.
- Keep changes scoped to the files listed in the plan.
- Do not revert unrelated dirty worktree changes.
- Use `D:\Hcworkspace\Anoconda3\envs\research_agent\python.exe` for tests.
- After each task, run the task-specific verification command and inspect the relevant diff.

## Tasks

1. Add tool registry and standardized tool-call records.
2. Add local fallback tool adapters.
3. Add ResearchAgent MCP-style tool facade.
4. Integrate tool registry with ResearchRun service, router, and UI health.
5. Add deterministic multi-agent synthesis.
6. Publish complete Obsidian-ready Knowledge Pack.
7. Add run result page signals and agent timeline.
8. Run M3/M4 verification and update execution tracker.
