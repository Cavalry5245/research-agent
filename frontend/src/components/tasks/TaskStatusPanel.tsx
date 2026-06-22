import type { TaskStatus } from "../../api/types";
import { StatusBadge } from "../status/StatusBadge";

interface TaskStatusPanelProps {
  task: TaskStatus | null;
  title?: string;
}

export function TaskStatusPanel({ task, title = "Task status" }: TaskStatusPanelProps) {
  if (!task) {
    return null;
  }

  const progress = Math.round((task.progress ?? 0) * 100);

  return (
    <div className="rounded-md border border-line bg-panel p-4">
      <div className="flex items-center justify-between gap-3">
        <div>
          <h2 className="text-sm font-semibold text-ink">{title}</h2>
          <p className="mt-1 text-xs text-muted">{task.job_id}</p>
        </div>
        <StatusBadge status={task.status} />
      </div>
      <div className="mt-3 h-2 overflow-hidden rounded-full bg-surface">
        <div className="h-full bg-accent" style={{ width: `${progress}%` }} />
      </div>
      <p className="mt-2 text-xs text-muted">{progress}% complete</p>
      {task.error && <p className="mt-2 text-sm text-red-700">{task.error}</p>}
    </div>
  );
}
