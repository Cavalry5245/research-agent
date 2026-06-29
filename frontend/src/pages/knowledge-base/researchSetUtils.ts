import type { KnowledgeBase, PaperListItem } from "../../api/types";

export function getMemberPapers(papers: PaperListItem[], set: KnowledgeBase) {
  const byId = new Map(papers.map((paper) => [paper.paper_id, paper]));
  return set.paper_ids.map(
    (paperId) => byId.get(paperId) ?? { paper_id: paperId, title: paperId, abstract: "" }
  );
}

export function getAvailablePapers(papers: PaperListItem[], set: KnowledgeBase) {
  const memberIds = new Set(set.paper_ids);
  return papers.filter((paper) => !memberIds.has(paper.paper_id));
}

export function percent(count?: number | null, total?: number | null) {
  if (!count || !total) return 0;
  return Math.round((count / total) * 100);
}

export function formatUpdatedAt(value?: string | null) {
  if (!value) return "Not updated yet";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "Not updated yet";
  return date.toLocaleDateString();
}
