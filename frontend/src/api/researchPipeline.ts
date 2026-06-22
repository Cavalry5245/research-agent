/**
 * Research Pipeline API Client
 *
 * TypeScript client for /research-pipeline endpoints.
 * All types use snake_case to match backend JSON responses.
 */

import { ApiError } from "./client";

// ==================== Type Definitions ====================

export type SourceMode = "web_search" | "zotero_only" | "hybrid";
export type RunStatus = "queued" | "running" | "completed" | "failed" | "cancelled" | "degraded";
export type StageStatus = "queued" | "running" | "completed" | "failed" | "degraded";
export type StageName = "planner" | "retriever" | "reader" | "synthesis" | "harness";
export type EventStageName = StageName | "runner";
export type VerificationStatus =
  | "supported"
  | "weak"
  | "unverified"
  | "numeric_trace_missing"
  | "conflict_detected";
export type ClaimType = "method" | "dataset" | "metric" | "result" | "limitation" | "gap" | "other";
export type ExtractionMode = "pdf" | "abstract_only";
export type EventLevel = "debug" | "info" | "warning" | "error";
export type PlanPhase = "initial" | "candidate_selection";

// ==================== Request Schemas ====================

export interface ResearchRunCreateRequest {
  question: string;
  source_mode?: SourceMode;
  zotero_collection_key?: string | null;
  max_reader_papers?: number;
  reader_concurrency?: number;
  year_start?: number | null;
  year_end?: number | null;
  venue_filter?: string[];
  keywords?: string[];
}

// ==================== Response Schemas ====================

export interface ResearchRunCreateResponse {
  run_id: string;
  status: RunStatus;
  created_at: string;
}

export interface ResearchRunSummary {
  run_id: string;
  question: string;
  source_mode: SourceMode;
  status: RunStatus;
  error: string | null;
  created_at: string;
}

export interface ResearchRunListResponse {
  count: number;
  runs: ResearchRunSummary[];
}

export interface PaperCandidate {
  paper_id: string;
  source: "semantic_scholar" | "arxiv" | "zotero";
  title: string;
  authors: string[];
  year: number | null;
  venue: string | null;
  abstract: string | null;
  doi: string | null;
  arxiv_id: string | null;
  semantic_scholar_id: string | null;
  zotero_item_id: string | null;
  url: string | null;
  pdf_url: string | null;
  local_pdf_path: string | null;
  citation_count: number | null;
  relevance_score: number | null;
  metadata: Record<string, unknown>;
}

export interface PaperCard {
  paper_id: string;
  status: StageStatus;
  extraction_mode: ExtractionMode;
  title: string;
  bibliographic_metadata: Record<string, unknown>;
  research_problem: string;
  method: string;
  datasets: string[];
  metrics: string[];
  key_results: string[];
  limitations: string[];
  assumptions: string[];
  future_work: string[];
  claims: Record<string, unknown>[];
  evidence: Record<string, unknown>[];
  error: string | null;
}

export interface ResearchPlan {
  id: string;
  run_id: string;
  version: number;
  phase: PlanPhase;
  plan_data: Record<string, unknown>;
  created_at: string;
}

export interface ResearchStage {
  id: string;
  run_id: string;
  stage: StageName;
  status: StageStatus;
  progress: number;
  message: string;
  started_at: string | null;
  completed_at: string | null;
  error: string | null;
  created_at: string;
}

export interface ResearchEvent {
  id: string;
  run_id: string;
  stage: EventStageName;
  level: EventLevel;
  message: string;
  payload: Record<string, unknown>;
  created_at: string;
}

export interface ResearchReport {
  id: string;
  run_id: string;
  status: string;
  markdown: string;
  template_version: string;
  created_at: string;
  updated_at: string;
}

export interface ResearchRunDetailResponse {
  run_id: string;
  question: string;
  normalized_question: string | null;
  source_mode: SourceMode;
  zotero_collection_key: string | null;
  status: RunStatus;
  max_reader_papers: number;
  reader_concurrency: number;
  year_start: number | null;
  year_end: number | null;
  venue_filter: string[];
  keywords: string[];
  created_at: string;
  started_at: string | null;
  completed_at: string | null;
  failed_at: string | null;
  cancelled_at: string | null;
  error: string | null;
  stages: ResearchStage[];
  events: ResearchEvent[];
  candidates: PaperCandidate[];
  cards: PaperCard[];
  plan: ResearchPlan | null;
  report: ResearchReport | null;
}

export interface ReportClaim {
  claim_text: string;
  claim_type: ClaimType;
  citation_ids: string[];
  evidence_ids: string[];
  verification_status: VerificationStatus;
  verification_reason: string;
}

export interface ReportWithClaimsResponse {
  markdown: string;
  claims: ReportClaim[];
  summary: Record<string, number>;
}

export interface ZoteroCollection {
  key: string;
  name: string;
  parent: string | null;
}

export interface ZoteroCollectionsResponse {
  collections: ZoteroCollection[];
  count: number;
}

export interface CancelRunResponse {
  message: string;
}

// ==================== Helper Functions ====================

async function handleResponse<T>(response: Response): Promise<T> {
  if (!response.ok) {
    let message = response.statusText || `Request failed with ${response.status}`;
    try {
      const payload = (await response.json()) as { detail?: string; message?: string };
      message = payload.detail || payload.message || message;
    } catch {
      message = response.statusText || message;
    }
    throw new ApiError(message, response.status);
  }

  return (await response.json()) as T;
}

async function handleTextResponse(response: Response): Promise<string> {
  if (!response.ok) {
    let message = response.statusText || `Request failed with ${response.status}`;
    try {
      const text = await response.text();
      message = text || message;
    } catch {
      message = response.statusText || message;
    }
    throw new ApiError(message, response.status);
  }

  return await response.text();
}

// ==================== API Functions ====================

/**
 * Create a new research run.
 *
 * @param request - Run creation parameters
 * @returns Created run with run_id, status, and created_at
 */
export async function createResearchRun(
  request: ResearchRunCreateRequest
): Promise<ResearchRunCreateResponse> {
  const response = await fetch("/research-pipeline/runs", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Accept: "application/json",
    },
    body: JSON.stringify(request),
  });

  return handleResponse<ResearchRunCreateResponse>(response);
}

/**
 * List research runs in reverse chronological order.
 *
 * @param limit - Maximum number of runs to return (default 50)
 * @returns List of runs with count
 */
export async function listResearchRuns(limit = 50): Promise<ResearchRunListResponse> {
  const response = await fetch(`/research-pipeline/runs?limit=${limit}`, {
    headers: { Accept: "application/json" },
  });

  return handleResponse<ResearchRunListResponse>(response);
}

/**
 * Get detailed information about a research run.
 *
 * @param runId - Run ID to retrieve
 * @returns Full run state with stages, events, candidates, cards, plan, and report
 */
export async function getResearchRunDetail(runId: string): Promise<ResearchRunDetailResponse> {
  const response = await fetch(`/research-pipeline/runs/${runId}`, {
    headers: { Accept: "application/json" },
  });

  return handleResponse<ResearchRunDetailResponse>(response);
}

/**
 * Cancel a research run.
 *
 * Only queued, running, or degraded runs can be cancelled.
 *
 * @param runId - Run ID to cancel
 * @returns Success message
 */
export async function cancelResearchRun(runId: string): Promise<CancelRunResponse> {
  const response = await fetch(`/research-pipeline/runs/${runId}/cancel`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Accept: "application/json",
    },
  });

  return handleResponse<CancelRunResponse>(response);
}

/**
 * Delete a research run and its persisted pipeline records.
 *
 * @param runId - Run ID to delete
 */
export async function deleteResearchRun(runId: string): Promise<void> {
  const response = await fetch(`/research-pipeline/runs/${runId}`, {
    method: "DELETE",
    headers: { Accept: "application/json" },
  });

  if (!response.ok) {
    let message = response.statusText || `Request failed with ${response.status}`;
    try {
      const payload = (await response.json()) as { detail?: string; message?: string };
      message = payload.detail || payload.message || message;
    } catch {
      message = response.statusText || message;
    }
    throw new ApiError(message, response.status);
  }
}

/**
 * Get report with claims and verification summary.
 *
 * @param runId - Run ID to retrieve report for
 * @returns Report markdown, claims, and summary
 */
export async function getReport(runId: string): Promise<ReportWithClaimsResponse> {
  const response = await fetch(`/research-pipeline/runs/${runId}/report`, {
    headers: { Accept: "application/json" },
  });

  return handleResponse<ReportWithClaimsResponse>(response);
}

/**
 * Download report as markdown text.
 *
 * @param runId - Run ID to retrieve report for
 * @returns Report markdown content
 */
export async function getReportMarkdown(runId: string): Promise<string> {
  const response = await fetch(`/research-pipeline/runs/${runId}/report.md`, {
    headers: { Accept: "text/markdown" },
  });

  return handleTextResponse(response);
}

/**
 * List Zotero collections from local Zotero instance.
 *
 * @param limit - Maximum number of collections to return (default 100)
 * @returns Collections list with count
 */
export async function listZoteroCollections(limit = 100): Promise<ZoteroCollectionsResponse> {
  const response = await fetch(`/research-pipeline/sources/zotero/collections?limit=${limit}`, {
    headers: { Accept: "application/json" },
  });

  return handleResponse<ZoteroCollectionsResponse>(response);
}
