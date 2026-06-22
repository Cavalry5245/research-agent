import { apiGet, apiJson } from "./client";
import type { NoteResponse } from "./types";

export function getPaperNote(paperId: string) {
  return apiGet<NoteResponse>(`/papers/${encodeURIComponent(paperId)}/note`);
}

export function generatePaperNote(paperId: string) {
  return apiJson<NoteResponse>(`/papers/${encodeURIComponent(paperId)}/note`);
}

export function getPaperNoteDownloadUrl(paperId: string) {
  return `/papers/${encodeURIComponent(paperId)}/download`;
}
