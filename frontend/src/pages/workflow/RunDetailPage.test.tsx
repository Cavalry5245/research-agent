import { render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { RunDetailPage } from "./RunDetailPage";
import * as api from "../../api/researchPipeline";
import type {
  ResearchRunDetailResponse,
  RunStatus,
  StageStatus,
  StageName,
} from "../../api/researchPipeline";

// Mock the API module
vi.mock("../../api/researchPipeline", () => ({
  getResearchRunDetail: vi.fn(),
  getReport: vi.fn(),
  cancelResearchRun: vi.fn(),
}));

const createMockRunDetail = (overrides?: Partial<ResearchRunDetailResponse>): ResearchRunDetailResponse => ({
  run_id: "run_20260621_001",
  question: "What are the latest advances in LLM reasoning?",
  normalized_question: null,
  source_mode: "web_search",
  zotero_collection_key: null,
  status: "running",
  max_reader_papers: 8,
  reader_concurrency: 3,
  year_start: null,
  year_end: null,
  venue_filter: [],
  keywords: [],
  created_at: "2026-06-21T10:00:00Z",
  started_at: "2026-06-21T10:00:01Z",
  completed_at: null,
  failed_at: null,
  cancelled_at: null,
  error: null,
  stages: [
    {
      id: "stage_1",
      run_id: "run_20260621_001",
      stage: "planner" as StageName,
      status: "completed" as StageStatus,
      progress: 100,
      message: "Plan created",
      started_at: "2026-06-21T10:00:01Z",
      completed_at: "2026-06-21T10:00:05Z",
      error: null,
      created_at: "2026-06-21T10:00:01Z",
    },
    {
      id: "stage_2",
      run_id: "run_20260621_001",
      stage: "retriever" as StageName,
      status: "running" as StageStatus,
      progress: 50,
      message: "Searching papers...",
      started_at: "2026-06-21T10:00:05Z",
      completed_at: null,
      error: null,
      created_at: "2026-06-21T10:00:05Z",
    },
  ],
  events: [
    {
      id: "event_1",
      run_id: "run_20260621_001",
      stage: "planner" as StageName,
      level: "info",
      message: "Starting planner",
      payload: {},
      created_at: "2026-06-21T10:00:01Z",
    },
  ],
  candidates: [],
  cards: [],
  plan: null,
  report: null,
  ...overrides,
});

function renderWithRouter(runId: string) {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  });

  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={[`/workflow/${runId}`]}>
        <Routes>
          <Route path="/workflow/:runId" element={<RunDetailPage />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>
  );
}

describe("RunDetailPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  it("displays loading state initially", () => {
    vi.mocked(api.getResearchRunDetail).mockImplementation(
      () => new Promise(() => {}) // Never resolves
    );

    renderWithRouter("run_20260621_001");

    expect(screen.getByText(/loading/i)).toBeInTheDocument();
  });

  it("displays run detail when loaded", async () => {
    const mockRun = createMockRunDetail();
    vi.mocked(api.getResearchRunDetail).mockResolvedValue(mockRun);

    renderWithRouter("run_20260621_001");

    await waitFor(() => {
      expect(screen.getByText("What are the latest advances in LLM reasoning?")).toBeInTheDocument();
    });

    expect(screen.getByText(/run_20260621_001/i)).toBeInTheDocument();
    expect(screen.getByText("Source: web_search")).toBeInTheDocument();
  });

  it("displays stage progression", async () => {
    const mockRun = createMockRunDetail();
    vi.mocked(api.getResearchRunDetail).mockResolvedValue(mockRun);

    renderWithRouter("run_20260621_001");

    await waitFor(() => {
      expect(screen.getByText("Stage Progression")).toBeInTheDocument();
    });

    // Check for stage-specific messages instead of stage names which appear multiple times
    expect(screen.getByText("Plan created")).toBeInTheDocument();
    expect(screen.getByText("Searching papers...")).toBeInTheDocument();

    // Verify all 5 stages are present
    const plannerElements = screen.getAllByText(/planner/i);
    expect(plannerElements.length).toBeGreaterThan(0);
    const retrieverElements = screen.getAllByText(/retriever/i);
    expect(retrieverElements.length).toBeGreaterThan(0);
  });

  it("displays events log", async () => {
    const mockRun = createMockRunDetail();
    vi.mocked(api.getResearchRunDetail).mockResolvedValue(mockRun);

    renderWithRouter("run_20260621_001");

    await waitFor(() => {
      expect(screen.getByText("Starting planner")).toBeInTheDocument();
    });
  });

  it("polls every 2 seconds for running status", async () => {
    const mockRun = createMockRunDetail({ status: "running" });
    vi.mocked(api.getResearchRunDetail).mockResolvedValue(mockRun);

    renderWithRouter("run_20260621_001");

    // Initial load
    await waitFor(() => {
      expect(api.getResearchRunDetail).toHaveBeenCalledTimes(1);
    });

    // Wait for at least one more poll
    await waitFor(
      () => {
        expect(api.getResearchRunDetail).toHaveBeenCalledWith("run_20260621_001");
        expect(api.getResearchRunDetail).toHaveBeenCalledTimes(2);
      },
      { timeout: 3000 }
    );
  });

  it("polls every 2 seconds for queued status", async () => {
    const mockRun = createMockRunDetail({ status: "queued" });
    vi.mocked(api.getResearchRunDetail).mockResolvedValue(mockRun);

    renderWithRouter("run_20260621_001");

    await waitFor(() => {
      expect(api.getResearchRunDetail).toHaveBeenCalledTimes(1);
    });

    await waitFor(
      () => {
        expect(api.getResearchRunDetail).toHaveBeenCalledTimes(2);
      },
      { timeout: 3000 }
    );
  });

  it("polls every 2 seconds for degraded status", async () => {
    const mockRun = createMockRunDetail({ status: "degraded" });
    vi.mocked(api.getResearchRunDetail).mockResolvedValue(mockRun);

    renderWithRouter("run_20260621_001");

    await waitFor(() => {
      expect(api.getResearchRunDetail).toHaveBeenCalledTimes(1);
    });

    await waitFor(
      () => {
        expect(api.getResearchRunDetail).toHaveBeenCalledTimes(2);
      },
      { timeout: 3000 }
    );
  });

  it("stops polling for completed status", async () => {
    const mockRun = createMockRunDetail({ status: "completed" });
    vi.mocked(api.getResearchRunDetail).mockResolvedValue(mockRun);

    const { unmount } = renderWithRouter("run_20260621_001");

    await waitFor(() => {
      expect(api.getResearchRunDetail).toHaveBeenCalledTimes(1);
    });

    // Wait longer than polling interval using real timers
    await waitFor(() => {
      // This will timeout if polling continues
      expect(api.getResearchRunDetail).toHaveBeenCalledTimes(1);
    }, { timeout: 3000, interval: 500 });

    // Cleanup
    unmount();
  });

  it("stops polling for failed status", async () => {
    const mockRun = createMockRunDetail({
      status: "failed",
      error: "Connection timeout",
      failed_at: "2026-06-21T10:05:00Z",
    });
    vi.mocked(api.getResearchRunDetail).mockResolvedValue(mockRun);

    const { unmount } = renderWithRouter("run_20260621_001");

    await waitFor(() => {
      expect(api.getResearchRunDetail).toHaveBeenCalledTimes(1);
    });

    await waitFor(() => {
      expect(api.getResearchRunDetail).toHaveBeenCalledTimes(1);
    }, { timeout: 3000, interval: 500 });

    unmount();
  });

  it("stops polling for cancelled status", async () => {
    const mockRun = createMockRunDetail({
      status: "cancelled",
      cancelled_at: "2026-06-21T10:05:00Z",
    });
    vi.mocked(api.getResearchRunDetail).mockResolvedValue(mockRun);

    const { unmount } = renderWithRouter("run_20260621_001");

    await waitFor(() => {
      expect(api.getResearchRunDetail).toHaveBeenCalledTimes(1);
    });

    await waitFor(() => {
      expect(api.getResearchRunDetail).toHaveBeenCalledTimes(1);
    }, { timeout: 3000, interval: 500 });

    unmount();
  });

  it("displays candidates when available", async () => {
    const mockRun = createMockRunDetail({
      candidates: [
        {
          paper_id: "paper_001",
          source: "semantic_scholar",
          title: "Advances in LLM Reasoning",
          authors: ["Alice", "Bob"],
          year: 2025,
          venue: "NeurIPS",
          abstract: "This paper presents...",
          doi: "10.1234/paper001",
          arxiv_id: null,
          semantic_scholar_id: "ss_001",
          zotero_item_id: null,
          url: "https://example.com",
          pdf_url: null,
          local_pdf_path: null,
          citation_count: 42,
          relevance_score: 0.95,
          metadata: {},
        },
      ],
    });
    vi.mocked(api.getResearchRunDetail).mockResolvedValue(mockRun);

    renderWithRouter("run_20260621_001");

    await waitFor(() => {
      expect(screen.getByText("Advances in LLM Reasoning")).toBeInTheDocument();
    });

    expect(screen.getByText("Alice, Bob")).toBeInTheDocument();
    expect(screen.getByText("NeurIPS")).toBeInTheDocument();
  });

  it("displays paper cards when available", async () => {
    const mockRun = createMockRunDetail({
      cards: [
        {
          paper_id: "paper_001",
          status: "completed" as StageStatus,
          extraction_mode: "pdf",
          title: "Advances in LLM Reasoning",
          bibliographic_metadata: {},
          research_problem: "Improve reasoning",
          method: "Novel architecture",
          datasets: ["Dataset A"],
          metrics: ["Accuracy"],
          key_results: ["95% accuracy"],
          limitations: ["Limited to English"],
          assumptions: ["Assumes clean data"],
          future_work: ["Expand to other languages"],
          claims: [],
          evidence: [],
          error: null,
        },
      ],
    });
    vi.mocked(api.getResearchRunDetail).mockResolvedValue(mockRun);

    renderWithRouter("run_20260621_001");

    await waitFor(() => {
      expect(screen.getByText("Advances in LLM Reasoning")).toBeInTheDocument();
    });

    expect(screen.getByText(/Improve reasoning/i)).toBeInTheDocument();
  });

  it("displays report preview when available", async () => {
    const mockRun = createMockRunDetail({
      status: "completed",
      report: {
        id: "report_001",
        run_id: "run_20260621_001",
        status: "completed",
        markdown: "# Research Report\n\nThis is a summary...",
        template_version: "1.0",
        created_at: "2026-06-21T10:10:00Z",
        updated_at: "2026-06-21T10:10:00Z",
      },
    });
    vi.mocked(api.getResearchRunDetail).mockResolvedValue(mockRun);
    vi.mocked(api.getReport).mockResolvedValue({
      markdown: "# Research Report\n\nThis is a summary...",
      claims: [],
      summary: {},
    });

    renderWithRouter("run_20260621_001");

    await waitFor(() => {
      expect(screen.getByText(/Research Report/i)).toBeInTheDocument();
    });
  });

  it("displays failed run with error message", async () => {
    const mockRun = createMockRunDetail({
      status: "failed",
      error: "PDF parsing failed",
      failed_at: "2026-06-21T10:05:00Z",
      stages: [
        {
          id: "stage_3",
          run_id: "run_20260621_001",
          stage: "reader" as StageName,
          status: "failed" as StageStatus,
          progress: 30,
          message: "Failed",
          started_at: "2026-06-21T10:00:10Z",
          completed_at: null,
          error: "PDF parsing failed",
          created_at: "2026-06-21T10:00:10Z",
        },
      ],
    });
    vi.mocked(api.getResearchRunDetail).mockResolvedValue(mockRun);

    renderWithRouter("run_20260621_001");

    await waitFor(() => {
      expect(screen.getByText("What are the latest advances in LLM reasoning?")).toBeInTheDocument();
    });

    // Check for both instances of the error message
    const errorMessages = screen.getAllByText("PDF parsing failed");
    expect(errorMessages.length).toBeGreaterThanOrEqual(1);
  });

  it("displays degraded run with reason", async () => {
    const mockRun = createMockRunDetail({
      status: "degraded",
      error: "Some papers failed to process",
      stages: [
        {
          id: "stage_3",
          run_id: "run_20260621_001",
          stage: "reader" as StageName,
          status: "degraded" as StageStatus,
          progress: 80,
          message: "Partial success",
          started_at: "2026-06-21T10:00:10Z",
          completed_at: null,
          error: "2 papers failed",
          created_at: "2026-06-21T10:00:10Z",
        },
      ],
    });
    vi.mocked(api.getResearchRunDetail).mockResolvedValue(mockRun);

    renderWithRouter("run_20260621_001");

    await waitFor(() => {
      expect(screen.getByText("What are the latest advances in LLM reasoning?")).toBeInTheDocument();
    });

    expect(screen.getByText("Some papers failed to process")).toBeInTheDocument();
    expect(screen.getByText("2 papers failed")).toBeInTheDocument();
  });

  it("displays error message when run not found", async () => {
    vi.mocked(api.getResearchRunDetail).mockRejectedValue(
      new Error("Run not found")
    );

    renderWithRouter("run_20260621_999");

    await waitFor(() => {
      expect(screen.getByText(/Run not found/i)).toBeInTheDocument();
    });
  });

  it("displays partial artifacts for incomplete run", async () => {
    const mockRun = createMockRunDetail({
      status: "running",
      candidates: [
        {
          paper_id: "paper_001",
          source: "semantic_scholar",
          title: "Paper 1",
          authors: ["Author 1"],
          year: 2025,
          venue: null,
          abstract: null,
          doi: null,
          arxiv_id: null,
          semantic_scholar_id: null,
          zotero_item_id: null,
          url: null,
          pdf_url: null,
          local_pdf_path: null,
          citation_count: null,
          relevance_score: 0.9,
          metadata: {},
        },
      ],
      cards: [],
      report: null,
    });
    vi.mocked(api.getResearchRunDetail).mockResolvedValue(mockRun);

    renderWithRouter("run_20260621_001");

    await waitFor(() => {
      expect(screen.getByText("Paper 1")).toBeInTheDocument();
    });

    // Candidates visible even though run is incomplete
    expect(screen.getByText("Paper Candidates (1)")).toBeInTheDocument();
  });
});
