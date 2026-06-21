import { describe, it, expect, beforeEach, vi } from "vitest";
import {
  createResearchRun,
  listResearchRuns,
  getResearchRunDetail,
  cancelResearchRun,
  getReport,
  getReportMarkdown,
  listZoteroCollections,
} from "./researchPipeline";
import { ApiError } from "./client";

// Mock fetch globally
const mockFetch = vi.fn();
global.fetch = mockFetch;

describe("researchPipeline API", () => {
  beforeEach(() => {
    mockFetch.mockReset();
  });

  describe("createResearchRun", () => {
    it("should create a new research run with minimal params", async () => {
      const mockResponse = {
        run_id: "run_20260621_001",
        status: "queued",
        created_at: "2026-06-21T10:00:00Z",
      };

      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => mockResponse,
      });

      const result = await createResearchRun({
        question: "What are the latest advances in LLM reasoning?",
      });

      expect(mockFetch).toHaveBeenCalledWith("/research-pipeline/runs", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Accept: "application/json",
        },
        body: JSON.stringify({
          question: "What are the latest advances in LLM reasoning?",
        }),
      });

      expect(result).toEqual(mockResponse);
    });

    it("should create a research run with full params", async () => {
      const mockResponse = {
        run_id: "run_20260621_002",
        status: "queued",
        created_at: "2026-06-21T10:00:00Z",
      };

      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => mockResponse,
      });

      const result = await createResearchRun({
        question: "What are the latest advances in LLM reasoning?",
        source_mode: "hybrid",
        zotero_collection_key: "ABC123",
        max_reader_papers: 10,
        reader_concurrency: 5,
        year_start: 2023,
        year_end: 2026,
        venue_filter: ["NeurIPS", "ICML"],
        keywords: ["reasoning", "chain-of-thought"],
      });

      expect(mockFetch).toHaveBeenCalledWith("/research-pipeline/runs", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Accept: "application/json",
        },
        body: JSON.stringify({
          question: "What are the latest advances in LLM reasoning?",
          source_mode: "hybrid",
          zotero_collection_key: "ABC123",
          max_reader_papers: 10,
          reader_concurrency: 5,
          year_start: 2023,
          year_end: 2026,
          venue_filter: ["NeurIPS", "ICML"],
          keywords: ["reasoning", "chain-of-thought"],
        }),
      });

      expect(result).toEqual(mockResponse);
    });

    it("should throw ApiError on 400 validation error", async () => {
      mockFetch.mockResolvedValueOnce({
        ok: false,
        status: 400,
        statusText: "Bad Request",
        json: async () => ({ detail: "Invalid question parameter" }),
      });

      await expect(
        createResearchRun({ question: "" })
      ).rejects.toThrow(ApiError);
    });

    it("should throw ApiError with correct message on validation error", async () => {
      mockFetch.mockResolvedValueOnce({
        ok: false,
        status: 400,
        statusText: "Bad Request",
        json: async () => ({ detail: "Invalid question parameter" }),
      });

      await expect(
        createResearchRun({ question: "" })
      ).rejects.toThrow("Invalid question parameter");
    });
  });

  describe("listResearchRuns", () => {
    it("should list runs with default limit", async () => {
      const mockResponse = {
        count: 2,
        runs: [
          {
            run_id: "run_20260621_002",
            status: "running",
            created_at: "2026-06-21T10:30:00Z",
          },
          {
            run_id: "run_20260621_001",
            status: "completed",
            created_at: "2026-06-21T10:00:00Z",
          },
        ],
      };

      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => mockResponse,
      });

      const result = await listResearchRuns();

      expect(mockFetch).toHaveBeenCalledWith("/research-pipeline/runs?limit=50", {
        headers: { Accept: "application/json" },
      });

      expect(result).toEqual(mockResponse);
    });

    it("should list runs with custom limit", async () => {
      const mockResponse = {
        count: 1,
        runs: [
          {
            run_id: "run_20260621_002",
            status: "running",
            created_at: "2026-06-21T10:30:00Z",
          },
        ],
      };

      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => mockResponse,
      });

      const result = await listResearchRuns(10);

      expect(mockFetch).toHaveBeenCalledWith("/research-pipeline/runs?limit=10", {
        headers: { Accept: "application/json" },
      });

      expect(result).toEqual(mockResponse);
    });
  });

  describe("getResearchRunDetail", () => {
    it("should get run detail", async () => {
      const mockResponse = {
        run_id: "run_20260621_001",
        question: "What are the latest advances in LLM reasoning?",
        normalized_question: "latest advances llm reasoning",
        source_mode: "hybrid",
        zotero_collection_key: null,
        status: "completed",
        max_reader_papers: 8,
        reader_concurrency: 3,
        year_start: null,
        year_end: null,
        venue_filter: [],
        keywords: [],
        created_at: "2026-06-21T10:00:00Z",
        started_at: "2026-06-21T10:00:05Z",
        completed_at: "2026-06-21T10:15:00Z",
        failed_at: null,
        cancelled_at: null,
        error: null,
        stages: [
          {
            id: "stage_001",
            run_id: "run_20260621_001",
            stage: "planner",
            status: "completed",
            progress: 1.0,
            message: "Planning completed",
            started_at: "2026-06-21T10:00:05Z",
            completed_at: "2026-06-21T10:02:00Z",
            error: null,
            created_at: "2026-06-21T10:00:05Z",
          },
        ],
        events: [],
        candidates: [],
        cards: [],
        plan: null,
        report: null,
      };

      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => mockResponse,
      });

      const result = await getResearchRunDetail("run_20260621_001");

      expect(mockFetch).toHaveBeenCalledWith("/research-pipeline/runs/run_20260621_001", {
        headers: { Accept: "application/json" },
      });

      expect(result).toEqual(mockResponse);
    });

    it("should throw ApiError on 404 not found", async () => {
      mockFetch.mockResolvedValueOnce({
        ok: false,
        status: 404,
        statusText: "Not Found",
        json: async () => ({ detail: "Run not found" }),
      });

      await expect(
        getResearchRunDetail("invalid_run_id")
      ).rejects.toThrow(ApiError);
    });

    it("should throw ApiError with correct message on 404", async () => {
      mockFetch.mockResolvedValueOnce({
        ok: false,
        status: 404,
        statusText: "Not Found",
        json: async () => ({ detail: "Run not found" }),
      });

      await expect(
        getResearchRunDetail("invalid_run_id")
      ).rejects.toThrow("Run not found");
    });
  });

  describe("cancelResearchRun", () => {
    it("should cancel a run successfully", async () => {
      const mockResponse = {
        message: "Run cancelled successfully",
      };

      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => mockResponse,
      });

      const result = await cancelResearchRun("run_20260621_001");

      expect(mockFetch).toHaveBeenCalledWith("/research-pipeline/runs/run_20260621_001/cancel", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Accept: "application/json",
        },
      });

      expect(result).toEqual(mockResponse);
    });

    it("should throw ApiError on 404 not found", async () => {
      mockFetch.mockResolvedValueOnce({
        ok: false,
        status: 404,
        statusText: "Not Found",
        json: async () => ({ detail: "Run not found" }),
      });

      await expect(
        cancelResearchRun("invalid_run_id")
      ).rejects.toThrow(ApiError);
    });

    it("should throw ApiError on 409 conflict (already completed)", async () => {
      mockFetch.mockResolvedValueOnce({
        ok: false,
        status: 409,
        statusText: "Conflict",
        json: async () => ({ detail: "Run already completed" }),
      });

      await expect(
        cancelResearchRun("run_20260621_001")
      ).rejects.toThrow(ApiError);
    });

    it("should throw ApiError with correct message on 409 conflict", async () => {
      mockFetch.mockResolvedValueOnce({
        ok: false,
        status: 409,
        statusText: "Conflict",
        json: async () => ({ detail: "Run already completed" }),
      });

      await expect(
        cancelResearchRun("run_20260621_001")
      ).rejects.toThrow("Run already completed");
    });
  });

  describe("getReport", () => {
    it("should get report with claims and summary", async () => {
      const mockResponse = {
        markdown: "# Research Report\n\nSummary of findings...",
        claims: [
          {
            claim_text: "GPT-4 achieves 92% accuracy on reasoning tasks",
            claim_type: "result",
            citation_ids: ["paper_001"],
            evidence_ids: ["evidence_001"],
            verification_status: "supported",
            verification_reason: "Direct evidence found in paper",
          },
        ],
        summary: {
          supported: 5,
          weak: 2,
          unverified: 1,
          numeric_trace_missing: 0,
          conflict_detected: 0,
        },
      };

      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => mockResponse,
      });

      const result = await getReport("run_20260621_001");

      expect(mockFetch).toHaveBeenCalledWith("/research-pipeline/runs/run_20260621_001/report", {
        headers: { Accept: "application/json" },
      });

      expect(result).toEqual(mockResponse);
    });

    it("should throw ApiError on 404 not found", async () => {
      mockFetch.mockResolvedValueOnce({
        ok: false,
        status: 404,
        statusText: "Not Found",
        json: async () => ({ detail: "Report not found" }),
      });

      await expect(
        getReport("invalid_run_id")
      ).rejects.toThrow(ApiError);
    });
  });

  describe("getReportMarkdown", () => {
    it("should get report as markdown text", async () => {
      const mockMarkdown = "# Research Report\n\nSummary of findings...";

      mockFetch.mockResolvedValueOnce({
        ok: true,
        text: async () => mockMarkdown,
      });

      const result = await getReportMarkdown("run_20260621_001");

      expect(mockFetch).toHaveBeenCalledWith("/research-pipeline/runs/run_20260621_001/report.md", {
        headers: { Accept: "text/markdown" },
      });

      expect(result).toBe(mockMarkdown);
    });

    it("should throw ApiError on 404 not found", async () => {
      mockFetch.mockResolvedValueOnce({
        ok: false,
        status: 404,
        statusText: "Not Found",
        text: async () => "Not Found",
      });

      await expect(
        getReportMarkdown("invalid_run_id")
      ).rejects.toThrow(ApiError);
    });
  });

  describe("listZoteroCollections", () => {
    it("should list Zotero collections with default limit", async () => {
      const mockResponse = {
        collections: [
          {
            key: "ABC123",
            name: "Machine Learning Papers",
            parent: null,
          },
          {
            key: "DEF456",
            name: "NLP Research",
            parent: null,
          },
        ],
        count: 2,
      };

      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => mockResponse,
      });

      const result = await listZoteroCollections();

      expect(mockFetch).toHaveBeenCalledWith("/research-pipeline/sources/zotero/collections?limit=100", {
        headers: { Accept: "application/json" },
      });

      expect(result).toEqual(mockResponse);
    });

    it("should list Zotero collections with custom limit", async () => {
      const mockResponse = {
        collections: [
          {
            key: "ABC123",
            name: "Machine Learning Papers",
            parent: null,
          },
        ],
        count: 1,
      };

      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => mockResponse,
      });

      const result = await listZoteroCollections(50);

      expect(mockFetch).toHaveBeenCalledWith("/research-pipeline/sources/zotero/collections?limit=50", {
        headers: { Accept: "application/json" },
      });

      expect(result).toEqual(mockResponse);
    });

    it("should throw ApiError on 503 service unavailable", async () => {
      mockFetch.mockResolvedValueOnce({
        ok: false,
        status: 503,
        statusText: "Service Unavailable",
        json: async () => ({ detail: "Zotero API unavailable" }),
      });

      await expect(
        listZoteroCollections()
      ).rejects.toThrow(ApiError);
    });

    it("should throw ApiError with correct message on 503", async () => {
      mockFetch.mockResolvedValueOnce({
        ok: false,
        status: 503,
        statusText: "Service Unavailable",
        json: async () => ({ detail: "Zotero API unavailable" }),
      });

      await expect(
        listZoteroCollections()
      ).rejects.toThrow("Zotero API unavailable");
    });
  });
});
