import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { PaperDetailPage } from "./PaperDetailPage";
import * as notesApi from "../../api/notes";
import * as papersApi from "../../api/papers";

vi.mock("../../api/notes", () => ({
  generatePaperNote: vi.fn(),
  getPaperNote: vi.fn(),
  getPaperNoteDownloadUrl: vi.fn((paperId: string) => `/papers/${paperId}/download`)
}));

vi.mock("../../api/papers", () => ({
  getPaperIndexStatus: vi.fn(),
  getPapers: vi.fn(),
  indexPaper: vi.fn(),
  parsePaper: vi.fn()
}));

function renderPage(route = "/papers/paper_001") {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } }
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={[route]}>
        <Routes>
          <Route path="/papers/:paperId" element={<PaperDetailPage />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>
  );
}

beforeEach(() => {
  vi.clearAllMocks();
  vi.mocked(papersApi.getPapers).mockResolvedValue({
    count: 1,
    papers: [{ paper_id: "paper_001", title: "Attention Survey", abstract: "Transformer attention methods." }]
  });
  vi.mocked(papersApi.getPaperIndexStatus).mockResolvedValue({
    paper_id: "paper_001",
    indexed: true,
    chunk_count: 12,
    sections: ["Abstract", "Methods"]
  });
  vi.mocked(notesApi.getPaperNote).mockResolvedValue({
    paper_id: "paper_001",
    note_path: "notes/paper_001_note.md",
    content: "# Paper note"
  });
  vi.mocked(notesApi.generatePaperNote).mockResolvedValue({
    paper_id: "paper_001",
    note_path: "notes/paper_001_note.md",
    content: "# New note",
    status: "generated"
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
});

describe("PaperDetailPage", () => {
  it("renders metadata, index status, and note preview", async () => {
    renderPage();

    await waitFor(() => expect(screen.getByText("Attention Survey")).toBeInTheDocument());
    expect(screen.getByText("12 chunks")).toBeInTheDocument();
    expect(screen.getByText("Abstract, Methods")).toBeInTheDocument();
    expect(screen.getByText("# Paper note")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /download/i })).toHaveAttribute("href", "/papers/paper_001/download");
  });

  it("triggers parse, index, and note generation actions", async () => {
    const user = userEvent.setup();
    renderPage();

    await waitFor(() => expect(screen.getByText("Attention Survey")).toBeInTheDocument());
    await user.click(screen.getByRole("button", { name: "Parse" }));
    await user.click(screen.getByRole("button", { name: "Index" }));
    await user.click(screen.getByRole("button", { name: "Generate" }));

    expect(papersApi.parsePaper).toHaveBeenCalledWith("paper_001");
    expect(papersApi.indexPaper).toHaveBeenCalledWith("paper_001");
    expect(notesApi.generatePaperNote).toHaveBeenCalledWith("paper_001");
  });

  it("shows not found state for unknown paper", async () => {
    renderPage("/papers/missing");

    await waitFor(() => expect(screen.getByText("Paper not found")).toBeInTheDocument());
  });
});
