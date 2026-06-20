import { clsx } from "clsx";

const toneByStatus: Record<string, string> = {
  ok: "bg-emerald-50 text-emerald-700 ring-emerald-200",
  available: "bg-emerald-50 text-emerald-700 ring-emerald-200",
  completed: "bg-emerald-50 text-emerald-700 ring-emerald-200",
  running: "bg-blue-50 text-blue-700 ring-blue-200",
  queued: "bg-slate-50 text-slate-700 ring-slate-200",
  degraded: "bg-amber-50 text-amber-700 ring-amber-200",
  fallback_active: "bg-amber-50 text-amber-700 ring-amber-200",
  unavailable: "bg-red-50 text-red-700 ring-red-200",
  failed: "bg-red-50 text-red-700 ring-red-200",
  cancelled: "bg-slate-100 text-slate-600 ring-slate-200"
};

interface StatusBadgeProps {
  status: string;
  label?: string;
}

export function StatusBadge({ status, label }: StatusBadgeProps) {
  const normalized = status.replace(/_/g, " ");
  return (
    <span
      className={clsx(
        "inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ring-1 ring-inset",
        toneByStatus[status] ?? "bg-slate-50 text-slate-700 ring-slate-200"
      )}
    >
      {label ?? normalized}
    </span>
  );
}
