import { useQuery } from "@tanstack/react-query";
import { getSystemStatus } from "../../api/system";
import { EmptyState } from "../../components/empty-state/EmptyState";
import { ErrorState } from "../../components/error-state/ErrorState";
import { StatusBadge } from "../../components/status/StatusBadge";

export function SettingsPage() {
  const { data, isLoading, error } = useQuery({
    queryKey: ["system-status"],
    queryFn: getSystemStatus
  });

  if (isLoading) {
    return <p className="text-sm text-muted">Loading settings...</p>;
  }

  if (error) {
    return <ErrorState title="Unable to load settings" message={(error as Error).message} />;
  }

  if (!data) {
    return <EmptyState title="No settings data" description="The backend returned no system status payload." />;
  }

  return (
    <div className="space-y-6">
      <section className="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-ink">Settings</h1>
          <p className="mt-2 max-w-3xl text-sm leading-6 text-muted">
            Read-only runtime configuration reported by the FastAPI backend.
          </p>
        </div>
        <StatusBadge status={data.status} />
      </section>

      <section className="grid gap-4 xl:grid-cols-2">
        <div className="rounded-md border border-line bg-panel p-4 shadow-panel">
          <h2 className="text-sm font-semibold text-ink">Models</h2>
          <dl className="mt-4 space-y-3 text-sm">
            {Object.entries(data.models).map(([name, model]) => (
              <div key={name} className="flex items-start justify-between gap-4">
                <dt className="text-muted">{name}</dt>
                <dd className="text-right text-ink">
                  <div className="font-medium">{model.model}</div>
                  <div className="text-xs text-muted">{model.provider}</div>
                  <StatusBadge status={model.configured ? "available" : "unavailable"} label={model.configured ? "configured" : "missing"} />
                </dd>
              </div>
            ))}
          </dl>
        </div>

        <div className="rounded-md border border-line bg-panel p-4 shadow-panel">
          <h2 className="text-sm font-semibold text-ink">Storage</h2>
          <dl className="mt-4 space-y-3 text-sm">
            <div><dt className="text-muted">Uploads</dt><dd className="break-all text-ink">{data.storage.upload_dir}</dd></div>
            <div><dt className="text-muted">Notes</dt><dd className="break-all text-ink">{data.storage.note_dir}</dd></div>
            <div><dt className="text-muted">Metadata</dt><dd className="break-all text-ink">{data.storage.metadata_dir}</dd></div>
            <div className="flex items-center justify-between"><dt className="text-muted">Writable</dt><dd><StatusBadge status={data.storage.writable ? "ok" : "failed"} label={data.storage.writable ? "yes" : "no"} /></dd></div>
          </dl>
        </div>
      </section>

      <section className="grid gap-4 xl:grid-cols-2">
        <div className="rounded-md border border-line bg-panel p-4 shadow-panel">
          <h2 className="text-sm font-semibold text-ink">Vector store</h2>
          <dl className="mt-4 space-y-3 text-sm">
            <div className="flex items-center justify-between"><dt className="text-muted">Available</dt><dd><StatusBadge status={data.vector_store.available ? "available" : "unavailable"} /></dd></div>
            <div><dt className="text-muted">Backend</dt><dd className="text-ink">{data.vector_store.backend ?? "unknown"}</dd></div>
            <div><dt className="text-muted">Chunks</dt><dd className="text-ink">{data.vector_store.chunk_count}</dd></div>
            {data.vector_store.store_path && <div><dt className="text-muted">Path</dt><dd className="break-all text-ink">{data.vector_store.store_path}</dd></div>}
          </dl>
        </div>

        <div className="rounded-md border border-line bg-panel p-4 shadow-panel">
          <h2 className="text-sm font-semibold text-ink">Integrations</h2>
          <div className="mt-4 space-y-3">
            {Object.entries(data.integrations).map(([name, integration]) => (
              <div key={name} className="rounded-md border border-line bg-surface p-3">
                <div className="flex items-center justify-between gap-3">
                  <span className="text-sm font-medium text-ink">{name}</span>
                  <StatusBadge status={integration.configured ? "available" : "unavailable"} label={integration.configured ? "configured" : "missing"} />
                </div>
                {(integration.local_api_url || integration.path) && (
                  <p className="mt-2 break-all text-xs text-muted">{integration.local_api_url ?? integration.path}</p>
                )}
              </div>
            ))}
          </div>
        </div>
      </section>
    </div>
  );
}
