import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { KnowledgeBasePage } from "./KnowledgeBasePage";
import * as kbApi from "../../api/knowledgeBase";
import * as papersApi from "../../api/papers";

vi.mock("../../api/knowledgeBase", () => ({
  addPaperToKnowledgeBase: vi.fn(),
  createKnowledgeBase: vi.fn(),
  getKnowledgeBases: vi.fn(),
  removePaperFromKnowledgeBase: vi.fn()
}));
vi.mock("../../api/papers", () => ({ getPapers: vi.fn() }));

function renderPage() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={client}><KnowledgeBasePage /></QueryClientProvider>);
}

beforeEach(() => {
  vi.clearAllMocks();
  vi.mocked(kbApi.getKnowledgeBases).mockResolvedValue({
    count: 1,
    knowledge_bases: [{ id: "kb_cv", name: "Computer Vision", description: "Vision papers", paper_ids: ["paper_001"] }]
  });
  vi.mocked(papersApi.getPapers).mockResolvedValue({
    count: 2,
    papers: [
      { paper_id: "paper_001", title: "Attention Survey", abstract: "A" },
      { paper_id: "paper_002", title: "RAG Systems", abstract: "B" }
    ]
  });
  vi.mocked(kbApi.createKnowledgeBase).mockResolvedValue({ id: "kb_nlp", name: "NLP", description: "", paper_ids: [] });
  vi.mocked(kbApi.addPaperToKnowledgeBase).mockResolvedValue({ id: "kb_cv", name: "Computer Vision", description: "", paper_ids: ["paper_001", "paper_002"] });
  vi.mocked(kbApi.removePaperFromKnowledgeBase).mockResolvedValue({ id: "kb_cv", name: "Computer Vision", description: "", paper_ids: [] });
});

describe("KnowledgeBasePage", () => {
  it("creates a knowledge base", async () => {
    const user = userEvent.setup();
    renderPage();

    await user.type(await screen.findByLabelText(/kb id/i), "kb_nlp");
    await user.type(screen.getByLabelText(/^name$/i), "NLP");
    await user.click(screen.getByRole("button", { name: /create/i }));

    expect(vi.mocked(kbApi.createKnowledgeBase).mock.calls[0][0]).toEqual({ kb_id: "kb_nlp", name: "NLP", description: "" });
  });

  it("adds and removes papers", async () => {
    const user = userEvent.setup();
    renderPage();

    await user.selectOptions(await screen.findByLabelText(/add paper/i), "paper_002");
    await user.click(screen.getByRole("button", { name: "Add" }));
    await user.click(screen.getByLabelText("Remove paper_001 from kb_cv"));

    expect(vi.mocked(kbApi.addPaperToKnowledgeBase).mock.calls[0][0]).toBe("kb_cv");
    expect(vi.mocked(kbApi.addPaperToKnowledgeBase).mock.calls[0][1]).toBe("paper_002");
    expect(vi.mocked(kbApi.removePaperFromKnowledgeBase).mock.calls[0][0]).toBe("kb_cv");
    expect(vi.mocked(kbApi.removePaperFromKnowledgeBase).mock.calls[0][1]).toBe("paper_001");
  });
});
