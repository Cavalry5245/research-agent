import { apiGet } from "./client";
import type { McpHealthItem } from "./system";

export interface ResearchRunStep {
  agent: string;
  status: string;
  progress: number;
}

export interface ResearchRun {
  run_id: string;
  collection_id: string;
  collection_name: string;
  goal: string;
  status: string;
  progress: number;
  steps: ResearchRunStep[];
  error?: string | null;
}

export interface ResearchRunListResponse {
  count: number;
  runs: ResearchRun[];
}

export interface ResearchRunToolsHealthResponse {
  tools: McpHealthItem[];
}

export function getResearchRuns() {
  return apiGet<ResearchRunListResponse>("/research-runs");
}

export function getResearchRunToolsHealth() {
  return apiGet<ResearchRunToolsHealthResponse>("/research-runs/tools/health");
}
