import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Trash2 } from "lucide-react";
import { Link } from "react-router-dom";
import { deleteResearchRun, listResearchRuns } from "../../api/researchPipeline";
import { StatusBadge } from "../../components/status/StatusBadge";
import { EmptyState } from "../../components/empty-state/EmptyState";
import { ErrorState } from "../../components/error-state/ErrorState";
import { useState } from "react";

export function WorkflowPage() {
  const queryClient = useQueryClient();
  const [confirmingRunId, setConfirmingRunId] = useState<string | null>(null);
  const [deleteError, setDeleteError] = useState<string | null>(null);

  const { data, isLoading, error } = useQuery({
    queryKey: ["researchRuns"],
    queryFn: () => listResearchRuns(50),
  });

  const deleteMutation = useMutation({
    mutationFn: deleteResearchRun,
    onSuccess: () => {
      setConfirmingRunId(null);
      setDeleteError(null);
      void queryClient.invalidateQueries({ queryKey: ["researchRuns"] });
    },
    onError: (err) => {
      setDeleteError(err instanceof Error ? err.message : "Failed to delete research run");
    },
  });

  if (isLoading) {
    return (
      <div className="p-6">
        <p className="text-sm text-muted">Loading research runs...</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="p-6">
        <ErrorState
          title="Failed to load research runs"
          message={error instanceof Error ? error.message : "Unknown error"}
        />
      </div>
    );
  }

  const runs = data?.runs ?? [];

  if (runs.length === 0) {
    return (
      <div className="p-6">
        <div className="mb-6">
          <EmptyState
            title="No research runs yet"
            description="Start your first research run to explore academic papers."
          />
        </div>
        <div className="flex justify-center">
          <Link
            to="/workflow/new"
            className="inline-flex items-center rounded-md bg-accent px-4 py-2 text-sm font-medium text-white hover:bg-accent-hover"
          >
            New Run
          </Link>
        </div>
      </div>
    );
  }

  return (
    <div className="p-6">
      <div className="mb-6 flex items-center justify-between">
        <h1 className="text-2xl font-semibold text-ink">Research Runs</h1>
        <Link
          to="/workflow/new"
          className="inline-flex items-center rounded-md bg-accent px-4 py-2 text-sm font-medium text-white hover:bg-accent-hover"
        >
          New Run
        </Link>
      </div>

      <div className="overflow-hidden rounded-md border border-line bg-panel">
        {deleteError && (
          <div className="border-b border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
            {deleteError}
          </div>
        )}
        <table className="w-full table-fixed divide-y divide-line">
          <thead className="bg-surface">
            <tr>
              <th className="w-56 px-4 py-3 text-left text-xs font-medium uppercase tracking-wide text-muted">
                Run ID
              </th>
              <th className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wide text-muted">
                Question
              </th>
              <th className="w-28 px-4 py-3 text-left text-xs font-medium uppercase tracking-wide text-muted">
                Source Mode
              </th>
              <th className="w-24 px-4 py-3 text-left text-xs font-medium uppercase tracking-wide text-muted">
                Status
              </th>
              <th className="w-36 px-4 py-3 text-left text-xs font-medium uppercase tracking-wide text-muted">
                Created
              </th>
              <th className="w-28 px-4 py-3 text-right text-xs font-medium uppercase tracking-wide text-muted">
                Actions
              </th>
            </tr>
          </thead>
          <tbody className="divide-y divide-line bg-panel">
            {runs.map((run) => {
              const confirming = confirmingRunId === run.run_id;
              const deleting =
                deleteMutation.isPending && deleteMutation.variables === run.run_id;

              return (
                <tr key={run.run_id} className="hover:bg-surface">
                  <td className="px-4 py-3">
                    <Link
                      to={`/workflow/${run.run_id}`}
                      className="block truncate text-sm font-medium text-accent hover:underline"
                      title={run.run_id}
                    >
                      {run.run_id}
                    </Link>
                  </td>
                  <td className="px-4 py-3">
                    <div className="max-w-md">
                      <p className="truncate text-sm text-ink" title={run.question}>
                        {run.question}
                      </p>
                      {run.error && (
                        <p className="mt-1 truncate text-xs text-red-600" title={run.error}>
                          Error: {run.error}
                        </p>
                      )}
                    </div>
                  </td>
                  <td className="px-4 py-3">
                    <span className="text-sm text-muted">{run.source_mode}</span>
                  </td>
                  <td className="px-4 py-3">
                    <StatusBadge status={run.status} />
                  </td>
                  <td className="px-4 py-3 text-xs text-muted">
                    {new Date(run.created_at).toLocaleString(undefined, { hour12: false })}
                  </td>
                  <td className="px-4 py-3">
                    <div className="flex justify-end gap-2">
                      {confirming ? (
                        <>
                          <button
                            type="button"
                            onClick={() => deleteMutation.mutate(run.run_id)}
                            disabled={deleting}
                            className="rounded border border-red-200 px-2 py-1 text-xs font-medium text-red-600 transition-colors hover:bg-red-50 disabled:cursor-not-allowed disabled:opacity-60"
                          >
                            {deleting ? "Deleting" : "Confirm"}
                          </button>
                          <button
                            type="button"
                            onClick={() => {
                              setConfirmingRunId(null);
                              setDeleteError(null);
                            }}
                            disabled={deleting}
                            className="rounded border border-line px-2 py-1 text-xs font-medium text-muted transition-colors hover:bg-gray-50 disabled:cursor-not-allowed disabled:opacity-60"
                          >
                            Cancel
                          </button>
                        </>
                      ) : (
                        <button
                          type="button"
                          onClick={() => {
                            setConfirmingRunId(run.run_id);
                            setDeleteError(null);
                          }}
                          className="inline-flex h-8 w-8 items-center justify-center rounded border border-line text-muted transition-colors hover:border-red-200 hover:bg-red-50 hover:text-red-600"
                          aria-label={`Delete ${run.run_id}`}
                          title="Delete run"
                        >
                          <Trash2 className="h-4 w-4" aria-hidden="true" />
                        </button>
                      )}
                    </div>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
