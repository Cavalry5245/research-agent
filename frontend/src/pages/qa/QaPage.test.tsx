import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { QaPage } from "./QaPage";
import * as papersApi from "../../api/papers";
import * as qaApi from "../../api/qa";

vi.mock("../../api/papers", () => ({ getPapers: vi.fn() }));
vi.mock("../../api/qa", () => ({ askQuestion: vi.fn() }));

function renderPage() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={client}><QaPage /></QueryClientProvider>);
}

beforeEach(() => {
  vi.clearAllMocks();
  vi.mocked(papersApi.getPapers).mockResolvedValue({
    count: 1,
    papers: [{ paper_id: "paper_001", title: "Attention Survey", abstract: "Abstract" }]
  });
  vi.mocked(qaApi.askQuestion).mockResolvedValue({
    question: "What is attention?",
    answer: "Attention weighs token interactions.",
    sources: [
      {
        paper_id: "paper_001",
        title: "Attention Survey",
        section: "Methods",
        chunk_id: "chunk_001",
        content: "Attention assigns weights.",
        score: 0.9
      }
    ]
  });
});

describe("QaPage", () => {
  it("submits a scoped QA request and renders answer sources", async () => {
    const user = userEvent.setup();
    renderPage();

    await user.type(screen.getByPlaceholderText(/what does the paper say/i), "What is attention?");
    await user.selectOptions(await screen.findByLabelText(/scope/i), "paper_001");
    await user.click(screen.getByRole("button", { name: "Ask" }));

    await waitFor(() => expect(screen.getByText("Attention weighs token interactions.")).toBeInTheDocument());
    expect(vi.mocked(qaApi.askQuestion).mock.calls[0][0]).toEqual({
      question: "What is attention?",
      paper_id: "paper_001",
      top_k: 5
    });
    expect(screen.getByText("Attention assigns weights.")).toBeInTheDocument();
  });
});
