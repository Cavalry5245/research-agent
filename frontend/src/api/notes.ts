import { ApiError, apiGet, apiJson } from "./client";
import type { NoteResponse, NoteStatusListResponse } from "./types";

export function getNoteStatuses() {
  return apiGet<NoteStatusListResponse>("/papers/notes/status");
}

export function getPaperNote(paperId: string) {
  return apiGet<NoteResponse>(`/papers/${encodeURIComponent(paperId)}/note`);
}

export function generatePaperNote(paperId: string) {
  return apiJson<NoteResponse>(`/papers/${encodeURIComponent(paperId)}/note`);
}

export function getPaperNoteDownloadUrl(paperId: string) {
  return `/papers/${encodeURIComponent(paperId)}/download`;
}

function parseDownloadFilename(contentDisposition: string | null, fallback: string) {
  if (!contentDisposition) {
    return fallback;
  }

  const utf8Match = contentDisposition.match(/filename\*=UTF-8''([^;]+)/i);
  if (utf8Match?.[1]) {
    return decodeURIComponent(utf8Match[1].trim());
  }

  const filenameMatch = contentDisposition.match(/filename="?([^";]+)"?/i);
  return filenameMatch?.[1]?.trim() || fallback;
}

async function parseDownloadError(response: Response) {
  try {
    const payload = (await response.json()) as { detail?: string; message?: string };
    return payload.detail || payload.message || response.statusText;
  } catch {
    return response.statusText || `Download failed with ${response.status}`;
  }
}

export async function downloadPaperNote(paperId: string) {
  const response = await fetch(getPaperNoteDownloadUrl(paperId), {
    headers: {
      Accept: "text/markdown, application/octet-stream"
    }
  });

  if (!response.ok) {
    throw new ApiError(await parseDownloadError(response), response.status);
  }

  const blob = await response.blob();
  const filename = parseDownloadFilename(
    response.headers.get("content-disposition"),
    `${paperId}_note.md`
  );
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  link.style.display = "none";
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}
