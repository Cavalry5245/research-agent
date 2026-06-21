import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { listResearchRuns } from "../../api/researchPipeline";
import { StatusBadge } from "../../components/status/StatusBadge";
import { EmptyState } from "../../components/empty-state/EmptyState";
import { ErrorState } from "../../components/error-state/ErrorState";

export function WorkflowPage() {
  const { data, isLoading, error } = useQuery({
    queryKey: ["researchRuns"],
    queryFn: () => listResearchRuns(50),
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
        <table className="min-w-full divide-y divide-line">
          <thead className="bg-surface">
            <tr>
              <th className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wide text-muted">
                Run ID
              </th>
              <th className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wide text-muted">
                Status
              </th>
              <th className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wide text-muted">
                Created
              </th>
            </tr>
          </thead>
          <tbody className="divide-y divide-line bg-panel">
            {runs.map((run) => (
              <tr key={run.run_id} className="hover:bg-surface">
                <td className="px-4 py-3">
                  <Link
                    to={`/workflow/${run.run_id}`}
                    className="text-sm font-medium text-accent hover:underline"
                  >
                    {run.run_id}
                  </Link>
                </td>
                <td className="px-4 py-3">
                  <StatusBadge status={run.status} />
                </td>
                <td className="px-4 py-3 text-sm text-muted">
                  {new Date(run.created_at).toLocaleString()}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
