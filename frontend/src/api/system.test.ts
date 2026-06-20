import { afterEach, describe, expect, it, vi } from "vitest";
import { ApiError } from "./client";
import { getSystemStatus } from "./system";

const okPayload = {
  project: "ResearchAgent",
  status: "ok",
  counts: { papers: 2, chunks: 10, tasks: 1, research_runs: 1 },
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
  vector_store: {
    available: true,
    backend: "json",
    store_path: "app/storage/vector_db/vector_store.json",
    chunk_count: 10,
    error: null
  },
  storage: {
    upload_dir: "app/storage/papers",
    note_dir: "app/storage/notes",
    metadata_dir: "app/storage/metadata",
    writable: true
  },
  integrations: {
    zotero: {
      enabled: true,
      configured: true,
      local_api_url: "http://127.0.0.1:23119/api/users/0"
    },
    obsidian: {
      enabled: true,
      configured: true,
      path: "app/storage/knowledge_packs"
    }
  },
  mcp_hub: []
};

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe("getSystemStatus", () => {
  it("returns typed system status JSON", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        json: async () => okPayload
      })
    );

    const result = await getSystemStatus();

    expect(fetch).toHaveBeenCalledWith("/system/status", {
      headers: { Accept: "application/json" }
    });
    expect(result.counts.papers).toBe(2);
    expect(result.models.embedding.batch_size).toBe(32);
  });

  it("throws ApiError with response detail on non-2xx status", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: false,
        status: 503,
        json: async () => ({ detail: "backend unavailable" })
      })
    );

    await expect(getSystemStatus()).rejects.toMatchObject({
      name: "ApiError",
      status: 503,
      message: "backend unavailable"
    } satisfies Partial<ApiError>);
  });
});
