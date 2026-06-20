import { useQuery } from "@tanstack/react-query";
import { Activity, Database, FileText, Workflow } from "lucide-react";
import { getSystemStatus } from "../../api/system";
import { EmptyState } from "../../components/empty-state/EmptyState";
import { ErrorState } from "../../components/error-state/ErrorState";
import { MetricCard } from "../../components/status/MetricCard";
import { StatusBadge } from "../../components/status/StatusBadge";

export function DashboardPage() {
  const { data, isLoading, error } = useQuery({
    queryKey: ["system-status"],
    queryFn: getSystemStatus
  });

  if (isLoading) {
    return <p className="text-sm text-muted">Loading dashboard</p>;
  }

  if (error) {
    return <ErrorState title="Unable to load dashboard" message={(error as Error).message} />;
  }

  if (!data) {
    return <EmptyState title="No status data" description="The backend returned an empty system status response." />;
  }

  const llm = data.models.llm;
  const embedding = data.models.embedding;

  return (
    <div className="space-y-6">
      <section className="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
        <div>
          <p className="text-sm font-medium text-accent">React Workspace</p>
          <h1 className="mt-1 text-3xl font-semibold text-ink">{data.project}</h1>
          <p className="mt-2 max-w-3xl text-sm leading-6 text-muted">
            Developer-console view for research runs, paper knowledge, MCP health, and agent activity.
          </p>
        </div>
        <StatusBadge status={data.status} />
      </section>

      <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-4" aria-label="System metrics">
        <MetricCard label="Papers" value={data.counts.papers} detail="Parsed metadata records" />
        <MetricCard label="Indexed chunks" value={data.counts.chunks} detail={data.vector_store.backend ?? "No vector backend"} />
        <MetricCard label="Background tasks" value={data.counts.tasks} detail="Queued, running, and recent jobs" />
        <MetricCard label="Research runs" value={data.counts.research_runs} detail="Zotero-driven workflow runs" />
      </section>

      <section className="grid gap-4 xl:grid-cols-[1fr_1.4fr]">
        <div className="rounded-md border border-line bg-panel p-4 shadow-panel">
          <div className="flex items-center gap-2">
            <Activity className="h-4 w-4 text-accent" aria-hidden="true" />
            <h2 className="text-sm font-semibold text-ink">Runtime</h2>
          </div>
          <dl className="mt-4 space-y-3 text-sm">
            <div className="flex items-center justify-between gap-4">
              <dt className="text-muted">LLM</dt>
              <dd className="font-medium text-ink">{llm.model}</dd>
            </div>
            <div className="flex items-center justify-between gap-4">
              <dt className="text-muted">Embedding</dt>
              <dd className="font-medium text-ink">{embedding.model}</dd>
            </div>
            <div className="flex items-center justify-between gap-4">
              <dt className="text-muted">Storage writable</dt>
              <dd>
                <StatusBadge status={data.storage.writable ? "ok" : "failed"} label={data.storage.writable ? "yes" : "no"} />
              </dd>
            </div>
            <div className="flex items-center justify-between gap-4">
              <dt className="text-muted">Vector store</dt>
              <dd>
                <StatusBadge status={data.vector_store.available ? "available" : "unavailable"} />
              </dd>
            </div>
          </dl>
        </div>

        <div className="rounded-md border border-line bg-panel p-4 shadow-panel">
          <div className="flex items-center gap-2">
            <Database className="h-4 w-4 text-accent" aria-hidden="true" />
            <h2 className="text-sm font-semibold text-ink">MCP Hub</h2>
          </div>
          <div className="mt-4 divide-y divide-line">
            {data.mcp_hub.length === 0 ? (
              <EmptyState title="No MCP health records" description="The backend returned no tool health rows." />
            ) : (
              data.mcp_hub.map((tool) => (
                <div key={`${tool.tool_name}-${tool.provider}`} className="flex items-start justify-between gap-4 py-3">
                  <div>
                    <p className="text-sm font-medium text-ink">{tool.tool_name}</p>
                    <p className="mt-1 text-xs text-muted">{tool.provider}: {tool.message}</p>
                  </div>
                  <StatusBadge status={tool.state} />
                </div>
              ))
            )}
          </div>
        </div>
      </section>

      <section className="grid gap-4 xl:grid-cols-2">
        <div className="rounded-md border border-line bg-panel p-4 shadow-panel">
          <div className="flex items-center gap-2">
            <FileText className="h-4 w-4 text-accent" aria-hidden="true" />
            <h2 className="text-sm font-semibold text-ink">Paper Knowledge</h2>
          </div>
          <p className="mt-3 text-sm leading-6 text-muted">
            Papers, notes, QA, comparison, and knowledge-base views are wired into the shell and will be migrated on top of this API foundation.
          </p>
        </div>
        <div className="rounded-md border border-line bg-panel p-4 shadow-panel">
          <div className="flex items-center gap-2">
            <Workflow className="h-4 w-4 text-accent" aria-hidden="true" />
            <h2 className="text-sm font-semibold text-ink">Workflow Console</h2>
          </div>
          <p className="mt-3 text-sm leading-6 text-muted">
            Research Workflow will use Zotero collection intake, research runs, Agent Timeline, Knowledge Pack outputs, and MCP Hub status.
          </p>
        </div>
      </section>
    </div>
  );
}
