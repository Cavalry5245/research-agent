import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ComparePage } from "./ComparePage";
import * as compareApi from "../../api/compare";
import * as papersApi from "../../api/papers";
import * as tasksApi from "../../api/tasks";

vi.mock("../../api/compare", () => ({ comparePapers: vi.fn() }));
vi.mock("../../api/papers", () => ({ getPapers: vi.fn() }));
vi.mock("../../api/tasks", () => ({ submitCompareTask: vi.fn() }));

function renderPage() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={client}><ComparePage /></QueryClientProvider>);
}

beforeEach(() => {
  vi.clearAllMocks();
  vi.mocked(papersApi.getPapers).mockResolvedValue({
    count: 2,
    papers: [
      { paper_id: "paper_001", title: "Attention Survey", abstract: "Abstract A" },
      { paper_id: "paper_002", title: "RAG Systems", abstract: "Abstract B" }
    ]
  });
  vi.mocked(compareApi.comparePapers).mockResolvedValue({
    paper_ids: ["paper_001", "paper_002"],
    status: "compared",
    output_path: "notes/compare.md",
    content: "# Comparison"
  });
  vi.mocked(tasksApi.submitCompareTask).mockResolvedValue({
    job_id: "job_compare_001",
    job_type: "paper_comparison",
    paper_ids: ["paper_001", "paper_002"],
    status: "queued",
    progress: 0,
    created_at: "2026-06-22T00:00:00Z",
    updated_at: "2026-06-22T00:00:00Z"
  });
});

describe("ComparePage", () => {
  it("runs synchronous comparison for two selected papers", async () => {
    const user = userEvent.setup();
    renderPage();

    await user.click(await screen.findByLabelText(/Attention Survey/i));
    await user.click(screen.getByLabelText(/RAG Systems/i));
    await user.click(screen.getByRole("button", { name: /compare now/i }));

    await waitFor(() => expect(screen.getByText("# Comparison")).toBeInTheDocument());
    expect(vi.mocked(compareApi.comparePapers).mock.calls[0][0]).toEqual(["paper_001", "paper_002"]);
  });

  it("submits a compare task", async () => {
    const user = userEvent.setup();
    renderPage();

    await user.click(await screen.findByLabelText(/Attention Survey/i));
    await user.click(screen.getByLabelText(/RAG Systems/i));
    await user.click(screen.getByRole("button", { name: /submit compare task/i }));

    expect(vi.mocked(tasksApi.submitCompareTask).mock.calls[0][0]).toEqual(["paper_001", "paper_002"]);
    await waitFor(() => expect(screen.getByText("job_compare_001")).toBeInTheDocument());
  });
});
