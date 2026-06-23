import { apiDelete, apiGet, apiJson, apiUpload } from "./client";
import type {
  DeletePaperResponse,
  LibraryIndexStatusResponse,
  PaperIndexDetailResponse,
  PaperListResponse,
  PaperTitleUpdateResponse,
  PaperUploadResponse,
  ParseStatusResponse,
  TaskStatus,
  ZoteroImportCollectionsResponse,
  ZoteroImportItemsResponse,
  ZoteroImportResponse
} from "./types";
export type { PaperListItem, PaperListResponse } from "./types";

export function getPapers() {
  return apiGet<PaperListResponse>("/papers");
}

export function uploadPaper(file: File) {
  return apiUpload<PaperUploadResponse>("/papers/upload", file);
}

export function parsePaper(paperId: string) {
  return apiJson<ParseStatusResponse>(`/papers/${encodeURIComponent(paperId)}/parse`);
}

export function indexPaper(paperId: string, force = false) {
  const query = force ? "?force=true" : "";
  return apiJson<TaskStatus>(`/papers/${encodeURIComponent(paperId)}/index${query}`);
}

export function updatePaperTitle(paperId: string, title: string) {
  return apiJson<PaperTitleUpdateResponse>(`/papers/${encodeURIComponent(paperId)}/title`, {
    method: "PATCH",
    body: { title }
  });
}

export function getPaperIndexStatus(paperId: string) {
  return apiGet<PaperIndexDetailResponse>(`/papers/${encodeURIComponent(paperId)}/index-status`);
}

export function getLibraryIndexStatus() {
  return apiGet<LibraryIndexStatusResponse>("/library/index-status");
}

export function deletePaper(paperId: string) {
  return apiDelete<DeletePaperResponse>(`/papers/${encodeURIComponent(paperId)}`);
}

export function listPaperZoteroCollections() {
  return apiGet<ZoteroImportCollectionsResponse>("/papers/zotero/collections");
}

export function listPaperZoteroCollectionItems(collectionKey: string) {
  return apiGet<ZoteroImportItemsResponse>(
    `/papers/zotero/collections/${encodeURIComponent(collectionKey)}/items`
  );
}

export function importPapersFromZotero(collectionKey: string, itemKeys: string[]) {
  return apiJson<ZoteroImportResponse>("/papers/zotero/import", {
    body: {
      collection_key: collectionKey,
      item_keys: itemKeys
    }
  });
}
