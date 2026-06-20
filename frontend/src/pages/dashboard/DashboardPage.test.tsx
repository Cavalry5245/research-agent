import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { DashboardPage } from "./DashboardPage";

function renderWithQuery(ui: React.ReactElement) {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } }
  });
  return render(<QueryClientProvider client={client}>{ui}</QueryClientProvider>);
}

const statusPayload = {
  project: "ResearchAgent",
  status: "ok",
  counts: { papers: 3, chunks: 21, tasks: 2, research_runs: 1 },
  models: {
    llm: { provider: "openai_compatible", model: "deepseek-chat", configured: true },
    embedding: {
      provider: "local",
      model: "bge-small-zh-v1.5",
      configured: true,
      device: "auto",
      batch_size: 32
    }
  },
  vector_store: { available: true, backend: "json", store_path: "store.json", chunk_count: 21, error: null },
  storage: {
    upload_dir: "app/storage/papers",
    note_dir: "app/storage/notes",
    metadata_dir: "app/storage/metadata",
    writable: true
  },
  integrations: {
    zotero: { enabled: true, configured: true, local_api_url: "http://127.0.0.1:23119/api/users/0" },
    obsidian: { enabled: true, configured: true, path: "app/storage/knowledge_packs" }
  },
  mcp_hub: [
    {
      tool_name: "ResearchAgent MCP Server",
      provider: "mcp_stdio",
      available: true,
      fallback_available: false,
      fallback_active: false,
      message: "available",
      tool_count: 7,
      state: "available"
    }
  ]
};

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe("DashboardPage", () => {
  it("renders system metrics from backend data", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        json: async () => statusPayload
      })
    );

    renderWithQuery(<DashboardPage />);

    expect(screen.getByText("Loading dashboard")).toBeInTheDocument();
    await waitFor(() => expect(screen.getByText("ResearchAgent")).toBeInTheDocument());
    expect(screen.getByText("3")).toBeInTheDocument();
    expect(screen.getByText("21")).toBeInTheDocument();
    expect(screen.getByText("ResearchAgent MCP Server")).toBeInTheDocument();
    expect(screen.getByText("deepseek-chat")).toBeInTheDocument();
  });

  it("renders an error state when the backend fails", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("network down")));

    renderWithQuery(<DashboardPage />);

    await waitFor(() => expect(screen.getByRole("alert")).toBeInTheDocument());
    expect(screen.getByText("Unable to load dashboard")).toBeInTheDocument();
  });
});
