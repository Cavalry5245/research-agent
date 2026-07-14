import { apiJson } from "./client";
import type { QAResponse } from "./types";

export interface AskQuestionRequest {
  question: string;
  paper_id?: string | null;
  top_k?: number;
  conversation_id?: string | null;
}

export function askQuestion(request: AskQuestionRequest) {
  return apiJson<QAResponse>("/qa", { body: request });
}
