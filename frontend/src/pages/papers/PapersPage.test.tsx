import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { BrowserRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { PapersPage } from "./PapersPage";
import * as papersApi from "../../api/papers";
import * as tasksApi from "../../api/tasks";

vi.mock("../../api/papers", () => ({
  deletePaper: vi.fn(),
  getLibraryIndexStatus: vi.fn(),
  getPapers: vi.fn(),
  importPapersFromZotero: vi.fn(),
  indexPaper: vi.fn(),
  listPaperZoteroCollectionItems: vi.fn(),
  listPaperZoteroCollections: vi.fn(),
  parsePaper: vi.fn(),
  uploadPaper: vi.fn()
}));

vi.mock("../../api/tasks", () => ({
  getTasks: vi.fn()
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
    {
      paper_id: "paper_001",
      title: "Attention Survey",
      abstract: "Transformer attention methods.",
      created_at: "2026-06-21T00:00:00Z",
      source: "upload" as const,
      source_id: null
    },
    {
      paper_id: "paper_002",
      title: "RAG Systems",
      abstract: "Retrieval augmented generation.",
      created_at: "2026-06-22T00:00:00Z",
      source: "zotero" as const,
      source_id: "ZOTERO2"
    }
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
  vi.mocked(papersApi.listPaperZoteroCollections).mockResolvedValue({
    collections: [{ key: "COLL1", name: "Remote Sensing", parent_key: null, num_items: 2 }],
    count: 1
  });
  vi.mocked(papersApi.listPaperZoteroCollectionItems).mockResolvedValue({
    collection_key: "COLL1",
    count: 2,
    items: [
      {
        key: "ITEM1",
        title: "New Zotero Paper",
        creators: ["Ada Lovelace"],
        year: 2026,
        doi: null,
        has_pdf: true,
        pdf_path: "paper.pdf",
        already_imported: false,
        existing_paper_id: null
      },
      {
        key: "ITEM2",
        title: "Already Imported",
        creators: [],
        year: null,
        doi: null,
        has_pdf: true,
        pdf_path: "old.pdf",
        already_imported: true,
        existing_paper_id: "paper_002"
      }
    ]
  });
  vi.mocked(papersApi.importPapersFromZotero).mockResolvedValue({
    imported: [{ item_key: "ITEM1", title: "New Zotero Paper", paper_id: "paper_003", status: "imported", reason: null }],
    skipped: [],
    failed: []
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
  vi.mocked(tasksApi.getTasks).mockResolvedValue({
    count: 1,
    jobs: [
      {
        job_id: "job_001",
        job_type: "paper_index",
        paper_id: "paper_001",
        paper_ids: [],
        status: "running",
        progress: 0.42,
        created_at: "2026-06-22T00:00:00Z",
        updated_at: "2026-06-22T00:00:01Z"
      }
    ]
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

  it("filters papers by index state and source", async () => {
    const user = userEvent.setup();
    renderPage();

    await waitFor(() => expect(screen.getByText("Attention Survey")).toBeInTheDocument());
    await user.selectOptions(screen.getByLabelText("Filter by index status"), "not_indexed");

    expect(screen.queryByText("Attention Survey")).not.toBeInTheDocument();
    expect(screen.getByText("RAG Systems")).toBeInTheDocument();

    await user.selectOptions(screen.getByLabelText("Filter by source"), "upload");
    expect(screen.getByText("No matching papers")).toBeInTheDocument();
  });

  it("imports selected PDFs from Zotero", async () => {
    const user = userEvent.setup();
    renderPage();

    await waitFor(() => expect(screen.getByText("Attention Survey")).toBeInTheDocument());
    await user.click(screen.getByRole("button", { name: "Import from Zotero" }));
    await waitFor(() => expect(screen.getByRole("option", { name: "Remote Sensing (2)" })).toBeInTheDocument());

    await user.selectOptions(screen.getByLabelText("Collection"), "COLL1");
    await waitFor(() => expect(screen.getByText("New Zotero Paper")).toBeInTheDocument());
    await user.click(screen.getByRole("checkbox", { name: /New Zotero Paper/i }));
    await user.click(screen.getByRole("button", { name: "Import selected (1)" }));

    expect(vi.mocked(papersApi.importPapersFromZotero).mock.calls[0]).toEqual(["COLL1", ["ITEM1"]]);
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

  it("shows row-level task state on the index button after starting indexing", async () => {
    const user = userEvent.setup();
    renderPage();

    await waitFor(() => expect(screen.getByText("Attention Survey")).toBeInTheDocument());
    await user.click(screen.getAllByRole("button", { name: "Index" })[0]);

    await waitFor(() => {
      expect(
        screen.getByRole("button", { name: /Queued|Indexing 42%/i })
      ).toBeInTheDocument();
    });
  });

  it("labels parse as re-parse for already ingested papers", async () => {
    renderPage();

    await waitFor(() => expect(screen.getByText("Attention Survey")).toBeInTheDocument());
    expect(screen.getAllByRole("button", { name: "Re-parse" }).length).toBeGreaterThan(0);
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
