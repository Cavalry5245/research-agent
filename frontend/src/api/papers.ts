import { apiGet } from "./client";

export interface PaperListItem {
  paper_id: string;
  title: string;
  abstract: string;
}

export interface PaperListResponse {
  count: number;
  papers: PaperListItem[];
}

export function getPapers() {
  return apiGet<PaperListResponse>("/papers");
}
