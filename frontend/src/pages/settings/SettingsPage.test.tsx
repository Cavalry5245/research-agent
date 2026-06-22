import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { SettingsPage } from "./SettingsPage";
import * as systemApi from "../../api/system";

vi.mock("../../api/system", () => ({ getSystemStatus: vi.fn() }));

function renderPage() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={client}><SettingsPage /></QueryClientProvider>);
}

beforeEach(() => {
  vi.clearAllMocks();
  vi.mocked(systemApi.getSystemStatus).mockResolvedValue({
    project: "ResearchAgent",
    status: "ok",
    counts: { papers: 2, chunks: 10, tasks: 0, research_runs: 0 },
    models: {
      llm: { provider: "openai_compatible", model: "deepseek-chat", configured: true },
      embedding: { provider: "local", model: "bge", configured: true, device: "cpu", batch_size: 32 }
    },
    vector_store: { available: true, backend: "json", store_path: "store.json", chunk_count: 10 },
    storage: { upload_dir: "uploads", note_dir: "notes", metadata_dir: "metadata", writable: true },
    integrations: {
      zotero: { enabled: true, configured: true, local_api_url: "http://127.0.0.1:23119" },
      obsidian: { enabled: false, configured: false, path: null }
    },
    mcp_hub: []
  });
});

describe("SettingsPage", () => {
  it("renders runtime settings from system status", async () => {
    renderPage();

    await waitFor(() => expect(screen.getByText("deepseek-chat")).toBeInTheDocument());
    expect(screen.getByText("uploads")).toBeInTheDocument();
    expect(screen.getByText("json")).toBeInTheDocument();
    expect(screen.getByText("http://127.0.0.1:23119")).toBeInTheDocument();
  });
});
