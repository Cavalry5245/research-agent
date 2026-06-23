import { FormEvent, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { RefreshCw } from "lucide-react";
import { getTraceStats, getTraces } from "../../api/monitor";
import { EmptyState } from "../../components/empty-state/EmptyState";
import { ErrorState } from "../../components/error-state/ErrorState";

export function MonitorPage() {
  const [conversationId, setConversationId] = useState("");
  const [agentId, setAgentId] = useState("");
  const [filters, setFilters] = useState({ conversationId: "", agentId: "" });

  const tracesQuery = useQuery({
    queryKey: ["traces", filters],
    queryFn: () => getTraces({ ...filters, limit: 100 })
  });

  const statsQuery = useQuery({
    queryKey: ["trace-stats"],
    queryFn: getTraceStats
  });

  const handleFilter = (event: FormEvent) => {
    event.preventDefault();
    setFilters({ conversationId: conversationId.trim(), agentId: agentId.trim() });
  };

  if (tracesQuery.error) {
    return <ErrorState title="Unable to load traces" message={(tracesQuery.error as Error).message} />;
  }

  return (
    <div className="space-y-6">
      <section className="flex flex-col gap-4 xl:flex-row xl:items-end xl:justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-ink">Monitor</h1>
          <p className="mt-2 max-w-3xl text-sm leading-6 text-muted">
            Inspect agent traces, routing actions, and latency statistics.
          </p>
        </div>
        <button
          type="button"
          onClick={() => {
            void tracesQuery.refetch();
            void statsQuery.refetch();
          }}
          className="inline-flex items-center gap-2 rounded-md border border-line px-3 py-2 text-sm font-medium text-muted hover:bg-surface"
        >
          <RefreshCw className="h-4 w-4" aria-hidden="true" />
          Refresh
        </button>
      </section>

      <section className="grid gap-4 md:grid-cols-4">
        <div className="rounded-md border border-line bg-panel p-4 shadow-panel">
          <p className="text-xs font-medium uppercase text-muted">Total traces</p>
          <p className="mt-2 text-2xl font-semibold text-ink">{statsQuery.data?.total_traces ?? 0}</p>
        </div>
        <div className="rounded-md border border-line bg-panel p-4 shadow-panel">
          <p className="text-xs font-medium uppercase text-muted">Avg latency</p>
          <p className="mt-2 text-2xl font-semibold text-ink">{statsQuery.data?.avg_duration_ms ?? 0} ms</p>
        </div>
        <div className="rounded-md border border-line bg-panel p-4 shadow-panel">
          <p className="text-xs font-medium uppercase text-muted">Agents</p>
          <p className="mt-2 text-2xl font-semibold text-ink">{Object.keys(statsQuery.data?.by_agent ?? {}).length}</p>
        </div>
        <div className="rounded-md border border-line bg-panel p-4 shadow-panel">
          <p className="text-xs font-medium uppercase text-muted">Actions</p>
          <p className="mt-2 text-2xl font-semibold text-ink">{Object.keys(statsQuery.data?.by_action ?? {}).length}</p>
        </div>
      </section>

      <form onSubmit={handleFilter} className="grid gap-3 rounded-md border border-line bg-panel p-4 shadow-panel md:grid-cols-[1fr_1fr_auto] md:items-end">
        <label className="block">
          <span className="text-xs font-medium uppercase text-muted">Conversation ID</span>
          <input value={conversationId} onChange={(event) => setConversationId(event.target.value)} className="mt-1 w-full rounded-md border border-line px-3 py-2 text-sm" />
        </label>
        <label className="block">
          <span className="text-xs font-medium uppercase text-muted">Agent ID</span>
          <input value={agentId} onChange={(event) => setAgentId(event.target.value)} className="mt-1 w-full rounded-md border border-line px-3 py-2 text-sm" />
        </label>
        <button type="submit" className="rounded-md bg-accent px-4 py-2 text-sm font-medium text-white hover:bg-accent-hover">Apply</button>
      </form>

      <section className="rounded-md border border-line bg-panel shadow-panel">
        <div className="border-b border-line p-4">
          <h2 className="text-sm font-semibold text-ink">Traces</h2>
        </div>
        {tracesQuery.isLoading ? (
          <p className="p-4 text-sm text-muted">Loading traces...</p>
        ) : (tracesQuery.data?.traces ?? []).length === 0 ? (
          <div className="p-4">
            <EmptyState title="No traces found" description="Run agent actions or change filters to see trace events." />
          </div>
        ) : (
          <div className="divide-y divide-line">
            {tracesQuery.data!.traces.map((trace) => (
              <article key={trace.id} className="p-4">
                <div className="flex flex-wrap items-center gap-3 text-xs text-muted">
                  <span>{trace.id}</span>
                  <span className="font-medium text-ink">{trace.agent_id}</span>
                  <span>{trace.action}</span>
                  {trace.conversation_id && <span>{trace.conversation_id}</span>}
                  {trace.duration_ms !== null && trace.duration_ms !== undefined && <span>{trace.duration_ms} ms</span>}
                  <span>{new Date(trace.created_at * 1000).toLocaleString(undefined, { hour12: false })}</span>
                </div>
                <pre className="mt-3 max-h-40 overflow-auto whitespace-pre-wrap rounded-md bg-surface p-3 text-xs text-ink">
                  {JSON.stringify({ input: trace.input_data, output: trace.output_data, metadata: trace.metadata }, null, 2)}
                </pre>
              </article>
            ))}
          </div>
        )}
      </section>
    </div>
  );
}
