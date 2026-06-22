import { apiGet } from "./client";
import type { TraceListResponse, TraceStatsResponse } from "./types";

interface TraceListOptions {
  conversationId?: string;
  agentId?: string;
  limit?: number;
}

export function getTraces(options: TraceListOptions = {}) {
  const params = new URLSearchParams();
  if (options.conversationId) params.set("conversation_id", options.conversationId);
  if (options.agentId) params.set("agent_id", options.agentId);
  if (options.limit) params.set("limit", String(options.limit));
  const query = params.toString();
  return apiGet<TraceListResponse>(`/api/traces${query ? `?${query}` : ""}`);
}

export function getTraceStats() {
  return apiGet<TraceStatsResponse>("/api/traces/stats");
}
