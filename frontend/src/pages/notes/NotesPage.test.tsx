import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { NotesPage } from "./NotesPage";
import * as notesApi from "../../api/notes";
import * as papersApi from "../../api/papers";

vi.mock("../../api/notes", () => ({
  downloadPaperNote: vi.fn(),
  generatePaperNote: vi.fn(),
  getNoteStatuses: vi.fn(),
  getPaperNote: vi.fn()
}));

vi.mock("../../api/papers", () => ({ getPapers: vi.fn() }));

function renderPage() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <NotesPage />
    </QueryClientProvider>
  );
}

beforeEach(() => {
  vi.clearAllMocks();
  vi.mocked(papersApi.getPapers).mockResolvedValue({
    count: 2,
    papers: [
      {
        paper_id: "paper_001",
        title: "Attention Survey",
        abstract: "Abstract",
        created_at: "2026-06-21T00:00:00Z",
        source: "upload",
        source_id: null
      },
      {
        paper_id: "paper_002",
        title: "RAG Systems",
        abstract: "Retrieval augmented generation.",
        created_at: "2026-06-22T00:00:00Z",
        source: "zotero",
        source_id: "ITEM2"
      }
    ]
  });
  vi.mocked(notesApi.getNoteStatuses).mockResolvedValue({
    count: 2,
    notes: [
      {
        paper_id: "paper_001",
        exists: true,
        note_path: "notes/paper_001_note.md",
        generated_at: "2026-06-22T00:00:00Z"
      },
      {
        paper_id: "paper_002",
        exists: false,
        note_path: null,
        generated_at: null
      }
    ]
  });
  vi.mocked(notesApi.getPaperNote).mockResolvedValue({
    paper_id: "paper_001",
    note_path: "notes/paper_001_note.md",
    content: "# Existing note"
  });
  vi.mocked(notesApi.generatePaperNote).mockResolvedValue({
    paper_id: "paper_002",
    note_path: "notes/paper_002_note.md",
    content: "# Generated note",
    status: "generated"
  });
  vi.mocked(notesApi.downloadPaperNote).mockResolvedValue(undefined);
});

describe("NotesPage", () => {
  it("renders note status metrics and rows", async () => {
    renderPage();

    await waitFor(() => expect(screen.getByText("Attention Survey")).toBeInTheDocument());

    expect(screen.getByText("Notes generated")).toBeInTheDocument();
    expect(screen.getByText("Missing notes")).toBeInTheDocument();
    expect(screen.getByText("generated")).toBeInTheDocument();
    expect(screen.getByText("missing")).toBeInTheDocument();
  });

  it("filters notes by search and status", async () => {
    const user = userEvent.setup();
    renderPage();

    await waitFor(() => expect(screen.getByText("Attention Survey")).toBeInTheDocument());
    await user.selectOptions(screen.getByLabelText("Filter notes"), "missing");

    expect(screen.queryByText("Attention Survey")).not.toBeInTheDocument();
    expect(screen.getByText("RAG Systems")).toBeInTheDocument();

    await user.type(screen.getByPlaceholderText(/search title/i), "attention");
    expect(screen.getByText("No matching papers")).toBeInTheDocument();
  });

  it("previews and downloads a generated note", async () => {
    const user = userEvent.setup();
    renderPage();

    await waitFor(() => expect(screen.getByText("Attention Survey")).toBeInTheDocument());
    await user.click(screen.getByRole("button", { name: /view/i }));

    await waitFor(() => expect(screen.getByRole("heading", { name: "Existing note" })).toBeInTheDocument());
    await user.click(screen.getByRole("button", { name: /download/i }));
    expect(vi.mocked(notesApi.downloadPaperNote).mock.calls[0][0]).toBe("paper_001");
  });

  it("generates a missing note", async () => {
    const user = userEvent.setup();
    renderPage();

    await waitFor(() => expect(screen.getByText("RAG Systems")).toBeInTheDocument());
    await user.click(screen.getByRole("button", { name: "Generate" }));

    expect(vi.mocked(notesApi.generatePaperNote).mock.calls[0][0]).toBe("paper_002");
  });

  it("requires confirmation before regenerating an existing note", async () => {
    const user = userEvent.setup();
    renderPage();

    await waitFor(() => expect(screen.getByText("Attention Survey")).toBeInTheDocument());
    await user.click(screen.getByRole("button", { name: "Regenerate" }));
    await user.click(screen.getByRole("button", { name: "Confirm" }));

    expect(vi.mocked(notesApi.generatePaperNote).mock.calls[0][0]).toBe("paper_001");
  });
});
