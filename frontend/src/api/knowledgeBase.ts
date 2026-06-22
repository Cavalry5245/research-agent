import { apiDelete, apiGet, apiJson } from "./client";
import type { KnowledgeBase, KnowledgeBaseListResponse } from "./types";

export function getKnowledgeBases() {
  return apiGet<KnowledgeBaseListResponse>("/kb");
}

export function createKnowledgeBase(payload: { kb_id: string; name: string; description?: string }) {
  return apiJson<KnowledgeBase>("/kb", { body: payload });
}

export function addPaperToKnowledgeBase(kbId: string, paperId: string) {
  return apiJson<KnowledgeBase>(`/kb/${encodeURIComponent(kbId)}/papers`, { body: { paper_id: paperId } });
}

export function removePaperFromKnowledgeBase(kbId: string, paperId: string) {
  return apiDelete<KnowledgeBase>(`/kb/${encodeURIComponent(kbId)}/papers/${encodeURIComponent(paperId)}`);
}
