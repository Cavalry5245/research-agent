import { apiGet } from "./client";

export interface TaskStatus {
  job_id: string;
  job_type: string;
  paper_id?: string | null;
  paper_ids?: string[] | null;
  status: "queued" | "running" | "completed" | "failed" | "cancelled";
  progress: number;
  error?: string | null;
  result?: Record<string, unknown> | null;
}

export interface TaskListResponse {
  count: number;
  jobs: TaskStatus[];
}

export function getTasks() {
  return apiGet<TaskListResponse>("/tasks");
}
