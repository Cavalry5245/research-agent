import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { NotesPage } from "./NotesPage";
import * as notesApi from "../../api/notes";
import * as papersApi from "../../api/papers";
import * as tasksApi from "../../api/tasks";

vi.mock("../../api/notes", () => ({
  generatePaperNote: vi.fn(),
  getPaperNote: vi.fn(),
  getPaperNoteDownloadUrl: vi.fn((paperId: string) => `/papers/${paperId}/download`)
}));

vi.mock("../../api/papers", () => ({ getPapers: vi.fn() }));
vi.mock("../../api/tasks", () => ({ submitNoteTask: vi.fn() }));

function renderPage() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={client}><NotesPage /></QueryClientProvider>);
}

beforeEach(() => {
  vi.clearAllMocks();
  vi.mocked(papersApi.getPapers).mockResolvedValue({
    count: 1,
    papers: [{ paper_id: "paper_001", title: "Attention Survey", abstract: "Abstract" }]
  });
  vi.mocked(notesApi.getPaperNote).mockResolvedValue({
    paper_id: "paper_001",
    note_path: "notes/paper_001.md",
    content: "# Existing note"
  });
  vi.mocked(notesApi.generatePaperNote).mockResolvedValue({
    paper_id: "paper_001",
    note_path: "notes/paper_001.md",
    content: "# Generated note",
    status: "generated"
  });
  vi.mocked(tasksApi.submitNoteTask).mockResolvedValue({
    job_id: "job_note_001",
    job_type: "note_generation",
    paper_id: "paper_001",
    paper_ids: [],
    status: "queued",
    progress: 0,
    created_at: "2026-06-22T00:00:00Z",
    updated_at: "2026-06-22T00:00:00Z"
  });
});

describe("NotesPage", () => {
  it("loads and previews the selected paper note", async () => {
    const user = userEvent.setup();
    renderPage();

    await user.selectOptions(await screen.findByLabelText(/select paper/i), "paper_001");

    await waitFor(() => expect(screen.getByText("# Existing note")).toBeInTheDocument());
    expect(screen.getByRole("link", { name: /download/i })).toHaveAttribute("href", "/papers/paper_001/download");
  });

  it("can generate a note and submit a background task", async () => {
    const user = userEvent.setup();
    renderPage();

    await user.selectOptions(await screen.findByLabelText(/select paper/i), "paper_001");
    await user.click(screen.getByRole("button", { name: /generate now/i }));
    await user.click(screen.getByRole("button", { name: /submit task/i }));

    expect(vi.mocked(notesApi.generatePaperNote).mock.calls[0][0]).toBe("paper_001");
    expect(vi.mocked(tasksApi.submitNoteTask).mock.calls[0][0]).toBe("paper_001");
  });
});
