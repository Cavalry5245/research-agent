import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { QaPage } from "./QaPage";
import * as papersApi from "../../api/papers";
import * as qaApi from "../../api/qa";
import type { QAResponse } from "../../api/types";

vi.mock("../../api/papers", () => ({ getPapers: vi.fn() }));
vi.mock("../../api/qa", () => ({ askQuestion: vi.fn() }));

function renderPage() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <QaPage />
    </QueryClientProvider>
  );
}

function deferred<T>() {
  let resolve!: (value: T) => void;
  let reject!: (reason?: unknown) => void;
  const promise = new Promise<T>((innerResolve, innerReject) => {
    resolve = innerResolve;
    reject = innerReject;
  });
  return { promise, resolve, reject };
}

const qaResponse: QAResponse = {
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
};

beforeEach(() => {
  vi.clearAllMocks();
  localStorage.clear();
  vi.mocked(papersApi.getPapers).mockResolvedValue({
    count: 1,
    papers: [{ paper_id: "paper_001", title: "Attention Survey", abstract: "Abstract" }]
  });
  vi.mocked(qaApi.askQuestion).mockResolvedValue(qaResponse);
});

describe("QaPage", () => {
  it("submits a scoped QA request and renders answer sources", async () => {
    const user = userEvent.setup();
    renderPage();

    await user.type(screen.getByPlaceholderText(/what does the paper say/i), "What is attention?");
    await user.selectOptions(await screen.findByLabelText(/scope/i), "paper_001");
    await user.click(screen.getByRole("button", { name: "Send" }));

    await waitFor(() => expect(screen.getByText("Attention weighs token interactions.")).toBeInTheDocument());
    expect(vi.mocked(qaApi.askQuestion).mock.calls[0][0]).toEqual({
      question: "What is attention?",
      paper_id: "paper_001",
      top_k: 5
    });
    expect(screen.queryByText("Attention assigns weights.")).not.toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Sources (1)" }));
    expect(screen.getByText("Attention assigns weights.")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Close sources" }));
    expect(screen.queryByText("Attention assigns weights.")).not.toBeInTheDocument();
  });

  it("shows a thinking message while the answer is pending", async () => {
    const user = userEvent.setup();
    const pending = deferred<QAResponse>();
    vi.mocked(qaApi.askQuestion).mockReturnValue(pending.promise);
    renderPage();

    await user.type(screen.getByPlaceholderText(/what does the paper say/i), "What is attention?");
    await user.click(screen.getByRole("button", { name: "Send" }));

    expect(screen.getByText("What is attention?")).toBeInTheDocument();
    expect(screen.getByText(/model is retrieving sources/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Thinking" })).toBeDisabled();

    pending.resolve(qaResponse);
    await waitFor(() => expect(screen.getByText("Attention weighs token interactions.")).toBeInTheDocument());
  });

  it("restores a saved conversation from localStorage", async () => {
    localStorage.setItem(
      "research-agent:qa:conversation:v1",
      JSON.stringify({
        paperId: "paper_001",
        topK: 7,
        messages: [
          {
            id: "user_saved",
            role: "user",
            content: "Saved question?",
            created_at: "2026-06-23T00:00:00Z",
            paper_id: "paper_001",
            top_k: 7
          },
          {
            id: "assistant_saved",
            role: "assistant",
            content: "Saved answer.",
            status: "done",
            created_at: "2026-06-23T00:00:01Z",
            sources: [],
            request: {
              question: "Saved question?",
              paper_id: "paper_001",
              top_k: 7
            }
          }
        ]
      })
    );

    renderPage();

    expect(screen.getByText("Saved question?")).toBeInTheDocument();
    expect(screen.getByText("Saved answer.")).toBeInTheDocument();
    expect(screen.getByLabelText(/top k/i)).toHaveValue(7);
  });

  it("clears the local conversation", async () => {
    const user = userEvent.setup();
    renderPage();

    await user.type(screen.getByPlaceholderText(/what does the paper say/i), "What is attention?");
    await user.click(screen.getByRole("button", { name: "Send" }));
    await waitFor(() => expect(screen.getByText("Attention weighs token interactions.")).toBeInTheDocument());

    await user.click(screen.getByRole("button", { name: "Clear conversation" }));

    expect(screen.queryByText("Attention weighs token interactions.")).not.toBeInTheDocument();
    expect(localStorage.getItem("research-agent:qa:conversation:v1")).toBeNull();
  });
});
