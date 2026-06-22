import { apiDelete, apiGet, apiJson } from "./client";
import type { TaskListResponse, TaskStatus } from "./types";
export type { TaskListResponse, TaskStatus } from "./types";

export function getTasks() {
  return apiGet<TaskListResponse>("/tasks");
}

export function getTask(jobId: string) {
  return apiGet<TaskStatus>(`/tasks/${encodeURIComponent(jobId)}`);
}

export function getTaskResult(jobId: string) {
  return apiGet<Record<string, unknown>>(`/tasks/${encodeURIComponent(jobId)}/result`);
}

export function cancelTask(jobId: string) {
  return apiDelete<TaskStatus>(`/tasks/${encodeURIComponent(jobId)}`);
}

export function retryTask(jobId: string) {
  return apiJson<{ original_job_id: string; retry_job: TaskStatus }>(`/tasks/${encodeURIComponent(jobId)}/retry`);
}

export function submitNoteTask(paperId: string) {
  return apiJson<TaskStatus>(`/tasks/note/${encodeURIComponent(paperId)}`);
}

export function submitCompareTask(paperIds: string[]) {
  return apiJson<TaskStatus>("/tasks/compare", { body: { paper_ids: paperIds } });
}
