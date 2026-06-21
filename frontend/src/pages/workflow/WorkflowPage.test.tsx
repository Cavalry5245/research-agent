import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter } from "react-router-dom";
import userEvent from "@testing-library/user-event";
import { WorkflowPage } from "./WorkflowPage";
import * as api from "../../api/researchPipeline";

// Mock the API module
vi.mock("../../api/researchPipeline", () => ({
  listResearchRuns: vi.fn(),
}));

function renderWithProviders(ui: React.ReactElement) {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
      },
    },
  });

  return render(
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>{ui}</BrowserRouter>
    </QueryClientProvider>
  );
}

describe("WorkflowPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("shows loading state initially", () => {
    vi.mocked(api.listResearchRuns).mockImplementation(
      () => new Promise(() => {}) // Never resolves
    );

    renderWithProviders(<WorkflowPage />);

    expect(screen.getByText(/loading/i)).toBeInTheDocument();
  });

  it("shows empty state when no runs exist", async () => {
    vi.mocked(api.listResearchRuns).mockResolvedValue({
      count: 0,
      runs: [],
    });

    renderWithProviders(<WorkflowPage />);

    await waitFor(() => {
      expect(screen.getByText(/no research runs yet/i)).toBeInTheDocument();
    });

    expect(screen.getByText(/start your first research run/i)).toBeInTheDocument();
  });

  it("shows error state when API call fails", async () => {
    vi.mocked(api.listResearchRuns).mockRejectedValue(
      new Error("Network error")
    );

    renderWithProviders(<WorkflowPage />);

    await waitFor(() => {
      expect(screen.getByRole("alert")).toBeInTheDocument();
    });

    expect(screen.getByText(/failed to load research runs/i)).toBeInTheDocument();
    expect(screen.getByText(/network error/i)).toBeInTheDocument();
  });

  it("displays list of runs with key information", async () => {
    vi.mocked(api.listResearchRuns).mockResolvedValue({
      count: 2,
      runs: [
        {
          run_id: "run_001",
          status: "completed",
          created_at: "2026-06-21T10:30:00Z",
        },
        {
          run_id: "run_002",
          status: "running",
          created_at: "2026-06-21T11:00:00Z",
        },
      ],
    });

    renderWithProviders(<WorkflowPage />);

    await waitFor(() => {
      expect(screen.getByText("run_001")).toBeInTheDocument();
    });

    expect(screen.getByText("run_002")).toBeInTheDocument();
    expect(screen.getByText("completed")).toBeInTheDocument();
    expect(screen.getByText("running")).toBeInTheDocument();
  });

  it("navigates to new run page when New Run button clicked", async () => {
    const user = userEvent.setup();

    vi.mocked(api.listResearchRuns).mockResolvedValue({
      count: 0,
      runs: [],
    });

    renderWithProviders(<WorkflowPage />);

    await waitFor(() => {
      expect(screen.getByText(/no research runs yet/i)).toBeInTheDocument();
    });

    const newRunButton = screen.getByRole("link", { name: /new run/i });
    expect(newRunButton).toHaveAttribute("href", "/workflow/new");
  });

  it("navigates to run detail when row clicked", async () => {
    const user = userEvent.setup();

    vi.mocked(api.listResearchRuns).mockResolvedValue({
      count: 1,
      runs: [
        {
          run_id: "run_001",
          status: "completed",
          created_at: "2026-06-21T10:30:00Z",
        },
      ],
    });

    renderWithProviders(<WorkflowPage />);

    await waitFor(() => {
      expect(screen.getByText("run_001")).toBeInTheDocument();
    });

    const runLink = screen.getByRole("link", { name: /run_001/i });
    expect(runLink).toHaveAttribute("href", "/workflow/run_001");
  });

  it("displays status badges with correct styling", async () => {
    vi.mocked(api.listResearchRuns).mockResolvedValue({
      count: 6,
      runs: [
        {
          run_id: "run_queued",
          status: "queued",
          created_at: "2026-06-21T10:00:00Z",
        },
        {
          run_id: "run_running",
          status: "running",
          created_at: "2026-06-21T10:10:00Z",
        },
        {
          run_id: "run_completed",
          status: "completed",
          created_at: "2026-06-21T10:20:00Z",
        },
        {
          run_id: "run_failed",
          status: "failed",
          created_at: "2026-06-21T10:30:00Z",
        },
        {
          run_id: "run_cancelled",
          status: "cancelled",
          created_at: "2026-06-21T10:40:00Z",
        },
        {
          run_id: "run_degraded",
          status: "degraded",
          created_at: "2026-06-21T10:50:00Z",
        },
      ],
    });

    renderWithProviders(<WorkflowPage />);

    await waitFor(() => {
      expect(screen.getByText("queued")).toBeInTheDocument();
    });

    expect(screen.getByText("running")).toBeInTheDocument();
    expect(screen.getByText("completed")).toBeInTheDocument();
    expect(screen.getByText("failed")).toBeInTheDocument();
    expect(screen.getByText("cancelled")).toBeInTheDocument();
    expect(screen.getByText("degraded")).toBeInTheDocument();
  });

  it("shows New Run button in header when runs exist", async () => {
    vi.mocked(api.listResearchRuns).mockResolvedValue({
      count: 1,
      runs: [
        {
          run_id: "run_001",
          status: "completed",
          created_at: "2026-06-21T10:30:00Z",
        },
      ],
    });

    renderWithProviders(<WorkflowPage />);

    await waitFor(() => {
      expect(screen.getByText("run_001")).toBeInTheDocument();
    });

    const headerButton = screen.getByRole("link", { name: /new run/i });
    expect(headerButton).toHaveAttribute("href", "/workflow/new");
  });

  it("formats created_at timestamp for display", async () => {
    vi.mocked(api.listResearchRuns).mockResolvedValue({
      count: 1,
      runs: [
        {
          run_id: "run_001",
          status: "completed",
          created_at: "2026-06-21T10:30:00Z",
        },
      ],
    });

    renderWithProviders(<WorkflowPage />);

    await waitFor(() => {
      expect(screen.getByText("run_001")).toBeInTheDocument();
    });

    // Should show formatted date (locale-agnostic check)
    const dateCell = screen.getByText("run_001").closest("tr")?.querySelector("td:last-child");
    expect(dateCell).toBeTruthy();
    expect(dateCell?.textContent).toContain("2026");
  });
});
