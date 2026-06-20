import { apiGet } from "./client";

export interface SystemStatusCounts {
  papers: number;
  chunks: number;
  tasks: number;
  research_runs: number;
}

export interface SystemStatusModelInfo {
  provider: string;
  model: string;
  configured: boolean;
  device?: string | null;
  batch_size?: number | null;
}

export interface SystemStatusVectorStore {
  available: boolean;
  backend?: string | null;
  store_path?: string | null;
  chunk_count: number;
  error?: string | null;
}

export interface SystemStatusStorage {
  upload_dir: string;
  note_dir: string;
  metadata_dir: string;
  writable: boolean;
}

export interface SystemStatusIntegration {
  enabled: boolean;
  configured: boolean;
  local_api_url?: string | null;
  path?: string | null;
}

export interface McpHealthItem {
  tool_name: string;
  provider: string;
  available: boolean;
  fallback_available: boolean;
  fallback_active: boolean;
  message: string;
  tool_count?: number | null;
  state: string;
}

export interface SystemStatus {
  project: string;
  status: string;
  counts: SystemStatusCounts;
  models: Record<string, SystemStatusModelInfo>;
  vector_store: SystemStatusVectorStore;
  storage: SystemStatusStorage;
  integrations: Record<string, SystemStatusIntegration>;
  mcp_hub: McpHealthItem[];
}

export function getSystemStatus() {
  return apiGet<SystemStatus>("/system/status");
}
