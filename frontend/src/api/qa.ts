import { apiJson } from "./client";
import type { QAResponse } from "./types";

interface AskQuestionRequest {
  question: string;
  paper_id?: string | null;
  top_k?: number;
}

export function askQuestion(request: AskQuestionRequest) {
  return apiJson<QAResponse>("/qa", { body: request });
}
