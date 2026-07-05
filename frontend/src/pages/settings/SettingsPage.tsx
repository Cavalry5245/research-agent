import { useQuery } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { getLlmOverride, setLlmOverride } from "../../api/client";
import { getSystemStatus } from "../../api/system";
import { EmptyState } from "../../components/empty-state/EmptyState";
import { ErrorState } from "../../components/error-state/ErrorState";
import { StatusBadge } from "../../components/status/StatusBadge";

const BYOK_PRESETS: Array<{ label: string; baseUrl: string; model: string }> = [
  { label: "DeepSeek", baseUrl: "https://api.deepseek.com/v1", model: "deepseek-chat" },
  { label: "SiliconFlow", baseUrl: "https://api.siliconflow.cn/v1", model: "deepseek-ai/DeepSeek-V3" },
  { label: "OpenAI", baseUrl: "https://api.openai.com/v1", model: "gpt-4o-mini" }
];

export function SettingsPage() {
  const { data, isLoading, error } = useQuery({
    queryKey: ["system-status"],
    queryFn: getSystemStatus
  });

  // BYOK form state — visitor's own LLM credentials, stored in localStorage.
  const [baseUrl, setBaseUrl] = useState("");
  const [apiKey, setApiKey] = useState("");
  const [model, setModel] = useState("");
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    const existing = getLlmOverride();
    if (existing) {
      setBaseUrl(existing.baseUrl);
      setApiKey(existing.apiKey);
      setModel(existing.model);
    }
  }, []);

  const handleSave = () => {
    setLlmOverride({ baseUrl: baseUrl.trim(), apiKey: apiKey.trim(), model: model.trim() });
    setSaved(true);
    window.setTimeout(() => setSaved(false), 2000);
  };

  const handleClear = () => {
    setLlmOverride(null);
    setBaseUrl("");
    setApiKey("");
    setModel("");
    setSaved(false);
  };

  const applyPreset = (preset: (typeof BYOK_PRESETS)[number]) => {
    setBaseUrl(preset.baseUrl);
    setModel(preset.model);
  };

  return (
    <div className="space-y-6">
      <section className="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-ink">Settings</h1>
          <p className="mt-2 max-w-3xl text-sm leading-6 text-muted">
            Bring your own LLM key (BYOK) for the demo, plus read-only runtime configuration reported by the FastAPI backend.
          </p>
        </div>
        <StatusBadge status={data?.status ?? "unknown"} />
      </section>

      {/* BYOK card */}
      <section className="rounded-md border border-line bg-panel p-4 shadow-panel">
        <div className="flex items-center justify-between">
          <h2 className="text-sm font-semibold text-ink">Bring Your Own Key (BYOK)</h2>
          {saved && <span className="text-xs text-emerald-600">Saved — your key will be used for new requests.</span>}
        </div>
        <p className="mt-2 text-xs leading-5 text-muted">
          Fill in your own OpenAI-compatible LLM credentials. They are stored only in this browser (localStorage) and
          sent per-request as <code>X-LLM-*</code> headers. The backend never persists your key. Leave empty to use the
          operator-configured model.
        </p>

        <div className="mt-4 flex flex-wrap gap-2">
          {BYOK_PRESETS.map((preset) => (
            <button
              key={preset.label}
              type="button"
              onClick={() => applyPreset(preset)}
              className="rounded border border-line bg-surface px-2 py-1 text-xs text-ink hover:bg-line"
            >
              {preset.label}
            </button>
          ))}
        </div>

        <div className="mt-4 grid gap-3">
          <label className="block text-xs text-muted">
            Base URL
            <input
              type="text"
              value={baseUrl}
              onChange={(e) => setBaseUrl(e.target.value)}
              placeholder="https://api.deepseek.com/v1"
              className="mt-1 w-full rounded border border-line bg-surface px-2 py-1.5 text-sm text-ink"
            />
          </label>
          <label className="block text-xs text-muted">
            API Key
            <input
              type="password"
              value={apiKey}
              onChange={(e) => setApiKey(e.target.value)}
              placeholder="sk-..."
              className="mt-1 w-full rounded border border-line bg-surface px-2 py-1.5 text-sm text-ink"
            />
          </label>
          <label className="block text-xs text-muted">
            Model
            <input
              type="text"
              value={model}
              onChange={(e) => setModel(e.target.value)}
              placeholder="deepseek-chat"
              className="mt-1 w-full rounded border border-line bg-surface px-2 py-1.5 text-sm text-ink"
            />
          </label>
        </div>

        <div className="mt-4 flex gap-2">
          <button
            type="button"
            onClick={handleSave}
            disabled={apiKey.trim().length === 0}
            className="rounded bg-ink px-3 py-1.5 text-xs font-medium text-surface disabled:opacity-40"
          >
            Save
          </button>
          <button
            type="button"
            onClick={handleClear}
            className="rounded border border-line bg-surface px-3 py-1.5 text-xs text-ink hover:bg-line"
          >
            Clear
          </button>
        </div>
      </section>

      {isLoading ? (
        <p className="text-sm text-muted">Loading settings...</p>
      ) : error ? (
        <ErrorState title="Unable to load settings" message={(error as Error).message} />
      ) : !data ? (
        <EmptyState title="No settings data" description="The backend returned no system status payload." />
      ) : (
        <>
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
        </>
      )}
    </div>
  );
}
