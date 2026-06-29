import { apiDelete, apiGet, apiJson } from "./client";
import type { KnowledgeBase, KnowledgeBaseCreatePayload, KnowledgeBaseListResponse } from "./types";

export function getKnowledgeBases() {
  return apiGet<KnowledgeBaseListResponse>("/kb");
}

export function createKnowledgeBase(payload: KnowledgeBaseCreatePayload) {
  return apiJson<KnowledgeBase>("/kb", { body: payload });
}

export function addPaperToKnowledgeBase(kbId: string, paperId: string) {
  return apiJson<KnowledgeBase>(`/kb/${encodeURIComponent(kbId)}/papers`, { body: { paper_id: paperId } });
}

export async function addPapersToKnowledgeBase(kbId: string, paperIds: string[]) {
  let latest: KnowledgeBase | null = null;
  for (const paperId of paperIds) {
    latest = await addPaperToKnowledgeBase(kbId, paperId);
  }
  return latest;
}

export function removePaperFromKnowledgeBase(kbId: string, paperId: string) {
  return apiDelete<KnowledgeBase>(`/kb/${encodeURIComponent(kbId)}/papers/${encodeURIComponent(paperId)}`);
}
