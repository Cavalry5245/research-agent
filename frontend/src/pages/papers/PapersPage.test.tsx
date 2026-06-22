import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { BrowserRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { PapersPage } from "./PapersPage";
import * as papersApi from "../../api/papers";

vi.mock("../../api/papers", () => ({
  deletePaper: vi.fn(),
  getLibraryIndexStatus: vi.fn(),
  getPapers: vi.fn(),
  indexPaper: vi.fn(),
  parsePaper: vi.fn(),
  uploadPaper: vi.fn()
}));

function renderPage() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } }
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <PapersPage />
      </BrowserRouter>
    </QueryClientProvider>
  );
}

const paperPayload = {
  count: 2,
  papers: [
    { paper_id: "paper_001", title: "Attention Survey", abstract: "Transformer attention methods." },
    { paper_id: "paper_002", title: "RAG Systems", abstract: "Retrieval augmented generation." }
  ]
};

beforeEach(() => {
  vi.clearAllMocks();
  vi.mocked(papersApi.getPapers).mockResolvedValue(paperPayload);
  vi.mocked(papersApi.getLibraryIndexStatus).mockResolvedValue({
    total_chunks: 8,
    paper_count: 1,
    papers: [{ paper_id: "paper_001", chunk_count: 8, sections: ["Abstract"] }]
  });
  vi.mocked(papersApi.uploadPaper).mockResolvedValue({
    paper_id: "paper_003",
    filename: "paper.pdf",
    status: "parsed",
    storage_path: "papers/paper.pdf"
  });
  vi.mocked(papersApi.parsePaper).mockResolvedValue({
    paper_id: "paper_001",
    status: "parsed",
    json_path: "metadata/paper_001.json"
  });
  vi.mocked(papersApi.indexPaper).mockResolvedValue({
    job_id: "job_001",
    job_type: "paper_index",
    paper_id: "paper_001",
    paper_ids: [],
    status: "queued",
    progress: 0,
    created_at: "2026-06-22T00:00:00Z",
    updated_at: "2026-06-22T00:00:00Z"
  });
  vi.mocked(papersApi.deletePaper).mockResolvedValue({
    paper_id: "paper_002",
    status: "deleted",
    deleted_files: ["metadata/paper_002.json"],
    deleted_chunks: 0
  });
});

describe("PapersPage", () => {
  it("renders paper rows and index metrics", async () => {
    renderPage();

    await waitFor(() => expect(screen.getByText("Attention Survey")).toBeInTheDocument());
    expect(screen.getByText("RAG Systems")).toBeInTheDocument();
    expect(screen.getByText("8")).toBeInTheDocument();
    expect(screen.getByText("indexed")).toBeInTheDocument();
    expect(screen.getByText("not indexed")).toBeInTheDocument();
  });

  it("filters papers by search text", async () => {
    const user = userEvent.setup();
    renderPage();

    await waitFor(() => expect(screen.getByText("Attention Survey")).toBeInTheDocument());
    await user.type(screen.getByPlaceholderText(/search title/i), "rag");

    expect(screen.queryByText("Attention Survey")).not.toBeInTheDocument();
    expect(screen.getByText("RAG Systems")).toBeInTheDocument();
  });

  it("uploads a selected PDF", async () => {
    const user = userEvent.setup();
    renderPage();

    await waitFor(() => expect(screen.getByText("Attention Survey")).toBeInTheDocument());
    const input = document.querySelector("input[type='file']") as HTMLInputElement;
    const file = new File(["pdf"], "paper.pdf", { type: "application/pdf" });
    await user.upload(input, file);
    await user.click(screen.getByRole("button", { name: /^upload$/i }));

    expect(vi.mocked(papersApi.uploadPaper).mock.calls[0][0]).toBe(file);
  });

  it("confirms before deleting a paper", async () => {
    const user = userEvent.setup();
    renderPage();

    await waitFor(() => expect(screen.getByLabelText("Delete paper_002")).toBeInTheDocument());
    await user.click(screen.getByLabelText("Delete paper_002"));
    await user.click(screen.getByRole("button", { name: "Confirm" }));

    expect(vi.mocked(papersApi.deletePaper).mock.calls[0][0]).toBe("paper_002");
  });

  it("shows empty state when no papers exist", async () => {
    vi.mocked(papersApi.getPapers).mockResolvedValue({ count: 0, papers: [] });

    renderPage();

    await waitFor(() => expect(screen.getByText("No papers yet")).toBeInTheDocument());
  });
});
