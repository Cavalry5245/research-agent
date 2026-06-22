import { apiJson } from "./client";
import type { CompareResponse } from "./types";

export function comparePapers(paperIds: string[]) {
  return apiJson<CompareResponse>("/papers/compare", { body: { paper_ids: paperIds } });
}
