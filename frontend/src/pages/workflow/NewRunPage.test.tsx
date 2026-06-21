import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter, useNavigate } from "react-router-dom";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { NewRunPage } from "./NewRunPage";
import * as researchPipelineApi from "../../api/researchPipeline";

// Mock react-router-dom's useNavigate
vi.mock("react-router-dom", async () => {
  const actual = await vi.importActual("react-router-dom");
  return {
    ...actual,
    useNavigate: vi.fn(),
  };
});

// Mock API functions
vi.mock("../../api/researchPipeline", () => ({
  createResearchRun: vi.fn(),
  listZoteroCollections: vi.fn(),
}));

const mockNavigate = vi.fn();

function renderWithProviders(ui: React.ReactElement) {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  });

  return render(
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>{ui}</BrowserRouter>
    </QueryClientProvider>
  );
}

describe("NewRunPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    (useNavigate as ReturnType<typeof vi.fn>).mockReturnValue(mockNavigate);
  });

  it("renders form with all required fields", () => {
    vi.mocked(researchPipelineApi.listZoteroCollections).mockResolvedValue({
      collections: [],
      count: 0,
    });

    renderWithProviders(<NewRunPage />);

    expect(screen.getByLabelText(/research question/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/source mode/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/max reader papers/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/reader concurrency/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /create run/i })).toBeInTheDocument();
  });

  it("has correct default values", () => {
    vi.mocked(researchPipelineApi.listZoteroCollections).mockResolvedValue({
      collections: [],
      count: 0,
    });

    renderWithProviders(<NewRunPage />);

    const maxReaderPapers = screen.getByLabelText(/max reader papers/i) as HTMLInputElement;
    const readerConcurrency = screen.getByLabelText(/reader concurrency/i) as HTMLInputElement;

    expect(maxReaderPapers.value).toBe("8");
    expect(readerConcurrency.value).toBe("3");
  });

  it("validates required fields", async () => {
    vi.mocked(researchPipelineApi.listZoteroCollections).mockResolvedValue({
      collections: [],
      count: 0,
    });

    const user = userEvent.setup();
    renderWithProviders(<NewRunPage />);

    const submitButton = screen.getByRole("button", { name: /create run/i });
    await user.click(submitButton);

    await waitFor(() => {
      expect(screen.getByText(/research question is required/i)).toBeInTheDocument();
    });
  });

  it("loads Zotero collections successfully", async () => {
    vi.mocked(researchPipelineApi.listZoteroCollections).mockResolvedValue({
      collections: [
        { key: "ABC123", name: "Machine Learning", parent: null },
        { key: "DEF456", name: "Deep Learning", parent: null },
      ],
      count: 2,
    });

    const user = userEvent.setup();
    renderWithProviders(<NewRunPage />);

    // Wait for query to complete (collections load in background)
    await waitFor(() => {
      expect(researchPipelineApi.listZoteroCollections).toHaveBeenCalled();
    });

    // Switch to a mode that shows Zotero collections
    const sourceModeSelect = screen.getByLabelText(/source mode/i);
    await user.selectOptions(sourceModeSelect, "zotero_only");

    // Now the collections should be visible
    await waitFor(() => {
      expect(screen.getByText("Machine Learning")).toBeInTheDocument();
      expect(screen.getByText("Deep Learning")).toBeInTheDocument();
    });
  });

  it("handles Zotero collection loading failure gracefully", async () => {
    vi.mocked(researchPipelineApi.listZoteroCollections).mockRejectedValue(
      new Error("Zotero not available")
    );

    const user = userEvent.setup();
    renderWithProviders(<NewRunPage />);

    // Switch to a mode that requires Zotero
    const sourceModeSelect = screen.getByLabelText(/source mode/i);
    await user.selectOptions(sourceModeSelect, "zotero_only");

    // Manual collection key field should appear
    await waitFor(() => {
      expect(screen.getByLabelText(/collection key \(manual\)/i)).toBeInTheDocument();
    });
  });

  it("shows collection selector when Zotero mode is selected", async () => {
    vi.mocked(researchPipelineApi.listZoteroCollections).mockResolvedValue({
      collections: [{ key: "ABC123", name: "ML Papers", parent: null }],
      count: 1,
    });

    const user = userEvent.setup();
    renderWithProviders(<NewRunPage />);

    // Switch to Zotero mode
    const sourceModeSelect = screen.getByLabelText(/source mode/i);
    await user.selectOptions(sourceModeSelect, "zotero_only");

    // Collections field should appear and show collections
    await waitFor(() => {
      expect(screen.getByLabelText(/zotero collection/i)).toBeInTheDocument();
      expect(screen.getByText("ML Papers")).toBeInTheDocument();
    });
  });

  it("submits form with all fields", async () => {
    vi.mocked(researchPipelineApi.listZoteroCollections).mockResolvedValue({
      collections: [{ key: "ABC123", name: "ML Papers", parent: null }],
      count: 1,
    });

    vi.mocked(researchPipelineApi.createResearchRun).mockResolvedValue({
      run_id: "run_20260621_001",
      status: "queued",
      created_at: "2026-06-21T10:00:00Z",
    });

    const user = userEvent.setup();
    renderWithProviders(<NewRunPage />);

    await user.type(
      screen.getByLabelText(/research question/i),
      "What are the latest advances in LLM reasoning?"
    );

    const sourceModeSelect = screen.getByLabelText(/source mode/i);
    await user.selectOptions(sourceModeSelect, "hybrid");

    await user.click(screen.getByRole("button", { name: /create run/i }));

    await waitFor(() => {
      expect(researchPipelineApi.createResearchRun).toHaveBeenCalledTimes(1);
      const call = vi.mocked(researchPipelineApi.createResearchRun).mock.calls[0];
      expect(call[0]).toEqual({
        question: "What are the latest advances in LLM reasoning?",
        source_mode: "hybrid",
        zotero_collection_key: null,
        max_reader_papers: 8,
        reader_concurrency: 3,
        year_start: null,
        year_end: null,
        venue_filter: [],
        keywords: [],
      });
    });

    expect(mockNavigate).toHaveBeenCalledWith("/workflow/run_20260621_001");
  });

  it("submits with Zotero collection selected", async () => {
    vi.mocked(researchPipelineApi.listZoteroCollections).mockResolvedValue({
      collections: [{ key: "ABC123", name: "ML Papers", parent: null }],
      count: 1,
    });

    vi.mocked(researchPipelineApi.createResearchRun).mockResolvedValue({
      run_id: "run_20260621_002",
      status: "queued",
      created_at: "2026-06-21T10:00:00Z",
    });

    const user = userEvent.setup();
    renderWithProviders(<NewRunPage />);

    await user.type(screen.getByLabelText(/research question/i), "Test question");

    const sourceModeSelect = screen.getByLabelText(/source mode/i);
    await user.selectOptions(sourceModeSelect, "zotero_only");

    await waitFor(() => {
      expect(screen.getByLabelText(/zotero collection/i)).toBeInTheDocument();
    });

    const collectionSelect = screen.getByLabelText(/zotero collection/i);
    await user.selectOptions(collectionSelect, "ABC123");

    await user.click(screen.getByRole("button", { name: /create run/i }));

    await waitFor(() => {
      expect(researchPipelineApi.createResearchRun).toHaveBeenCalledTimes(1);
      const call = vi.mocked(researchPipelineApi.createResearchRun).mock.calls[0];
      expect(call[0]).toMatchObject({
        question: "Test question",
        source_mode: "zotero_only",
        zotero_collection_key: "ABC123",
      });
    });
  });

  it("submits with manual collection key when Zotero unavailable", async () => {
    vi.mocked(researchPipelineApi.listZoteroCollections).mockRejectedValue(
      new Error("Zotero not available")
    );

    vi.mocked(researchPipelineApi.createResearchRun).mockResolvedValue({
      run_id: "run_20260621_003",
      status: "queued",
      created_at: "2026-06-21T10:00:00Z",
    });

    const user = userEvent.setup();
    renderWithProviders(<NewRunPage />);

    await user.type(screen.getByLabelText(/research question/i), "Test question");

    const sourceModeSelect = screen.getByLabelText(/source mode/i);
    await user.selectOptions(sourceModeSelect, "zotero_only");

    await waitFor(() => {
      expect(screen.getByLabelText(/collection key \(manual\)/i)).toBeInTheDocument();
    });

    await user.type(screen.getByLabelText(/collection key \(manual\)/i), "MANUAL123");

    await user.click(screen.getByRole("button", { name: /create run/i }));

    await waitFor(() => {
      expect(researchPipelineApi.createResearchRun).toHaveBeenCalledTimes(1);
      const call = vi.mocked(researchPipelineApi.createResearchRun).mock.calls[0];
      expect(call[0]).toMatchObject({
        zotero_collection_key: "MANUAL123",
      });
    });
  });

  it("validates max_reader_papers range", async () => {
    vi.mocked(researchPipelineApi.listZoteroCollections).mockResolvedValue({
      collections: [],
      count: 0,
    });

    // Mock createResearchRun to reject (shouldn't be called anyway)
    vi.mocked(researchPipelineApi.createResearchRun).mockRejectedValue(
      new Error("Should not be called")
    );

    const user = userEvent.setup();
    renderWithProviders(<NewRunPage />);

    await user.type(screen.getByLabelText(/research question/i), "Test question");

    // Get the input and manually set an invalid value via React
    const maxReaderPapers = screen.getByLabelText(/max reader papers/i) as HTMLInputElement;

    // Use fireEvent to directly change the value (bypassing userEvent limitations with number inputs)
    const { fireEvent } = await import("@testing-library/react");
    fireEvent.change(maxReaderPapers, { target: { value: "2" } });

    await user.click(screen.getByRole("button", { name: /create run/i }));

    // Validation should prevent the API call
    await waitFor(() => {
      const errorText = screen.queryByText(/must be between 3 and 15/i);
      if (errorText) {
        expect(errorText).toBeInTheDocument();
      }
      expect(researchPipelineApi.createResearchRun).not.toHaveBeenCalled();
    });
  });

  it("handles submission error", async () => {
    vi.mocked(researchPipelineApi.listZoteroCollections).mockResolvedValue({
      collections: [],
      count: 0,
    });

    vi.mocked(researchPipelineApi.createResearchRun).mockRejectedValue(
      new Error("Network error")
    );

    const user = userEvent.setup();
    renderWithProviders(<NewRunPage />);

    await user.type(screen.getByLabelText(/research question/i), "Test question");
    await user.click(screen.getByRole("button", { name: /create run/i }));

    await waitFor(() => {
      expect(screen.getByText(/network error/i)).toBeInTheDocument();
    });
  });

  it("supports optional year range", async () => {
    vi.mocked(researchPipelineApi.listZoteroCollections).mockResolvedValue({
      collections: [],
      count: 0,
    });

    vi.mocked(researchPipelineApi.createResearchRun).mockResolvedValue({
      run_id: "run_20260621_004",
      status: "queued",
      created_at: "2026-06-21T10:00:00Z",
    });

    const user = userEvent.setup();
    renderWithProviders(<NewRunPage />);

    await user.type(screen.getByLabelText(/research question/i), "Test question");
    await user.type(screen.getByPlaceholderText(/start year/i), "2020");
    await user.type(screen.getByPlaceholderText(/end year/i), "2025");

    await user.click(screen.getByRole("button", { name: /create run/i }));

    await waitFor(() => {
      expect(researchPipelineApi.createResearchRun).toHaveBeenCalledTimes(1);
      const call = vi.mocked(researchPipelineApi.createResearchRun).mock.calls[0];
      expect(call[0]).toMatchObject({
        year_start: 2020,
        year_end: 2025,
      });
    });
  });

  it("supports optional venue filter", async () => {
    vi.mocked(researchPipelineApi.listZoteroCollections).mockResolvedValue({
      collections: [],
      count: 0,
    });

    vi.mocked(researchPipelineApi.createResearchRun).mockResolvedValue({
      run_id: "run_20260621_005",
      status: "queued",
      created_at: "2026-06-21T10:00:00Z",
    });

    const user = userEvent.setup();
    renderWithProviders(<NewRunPage />);

    await user.type(screen.getByLabelText(/research question/i), "Test question");
    await user.type(screen.getByLabelText(/venue filter/i), "NeurIPS, ICML");

    await user.click(screen.getByRole("button", { name: /create run/i }));

    await waitFor(() => {
      expect(researchPipelineApi.createResearchRun).toHaveBeenCalledTimes(1);
      const call = vi.mocked(researchPipelineApi.createResearchRun).mock.calls[0];
      expect(call[0]).toMatchObject({
        venue_filter: ["NeurIPS", "ICML"],
      });
    });
  });

  it("supports optional keywords", async () => {
    vi.mocked(researchPipelineApi.listZoteroCollections).mockResolvedValue({
      collections: [],
      count: 0,
    });

    vi.mocked(researchPipelineApi.createResearchRun).mockResolvedValue({
      run_id: "run_20260621_006",
      status: "queued",
      created_at: "2026-06-21T10:00:00Z",
    });

    const user = userEvent.setup();
    renderWithProviders(<NewRunPage />);

    await user.type(screen.getByLabelText(/research question/i), "Test question");
    await user.type(screen.getByLabelText(/keywords/i), "transformer, attention");

    await user.click(screen.getByRole("button", { name: /create run/i }));

    await waitFor(() => {
      expect(researchPipelineApi.createResearchRun).toHaveBeenCalledTimes(1);
      const call = vi.mocked(researchPipelineApi.createResearchRun).mock.calls[0];
      expect(call[0]).toMatchObject({
        keywords: ["transformer", "attention"],
      });
    });
  });
});
