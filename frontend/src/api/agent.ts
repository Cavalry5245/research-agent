import { apiJson } from "./client";
import type { AgentExecuteRequest, AgentExecuteResponse } from "./types";

export function executeAgent(request: AgentExecuteRequest) {
  return apiJson<AgentExecuteResponse>("/agent/execute", { body: request });
}
