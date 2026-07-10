import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { QaPage } from "./QaPage";
import * as conversationApi from "../../api/conversations";
import * as papersApi from "../../api/papers";
import * as qaApi from "../../api/qa";
import type { ConversationDetail, ConversationListResponse, QAResponse } from "../../api/types";
import { ApiError } from "../../api/client";

vi.mock("../../api/papers", () => ({ getPapers: vi.fn() }));
vi.mock("../../api/qa", () => ({ askQuestion: vi.fn() }));
vi.mock("../../api/conversations", () => ({
  listConversations: vi.fn(),
  getConversation: vi.fn(),
  deleteConversation: vi.fn()
}));

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
  const promise = new Promise<T>((innerResolve) => {
    resolve = innerResolve;
  });
  return { promise, resolve };
}

async function ask(user: ReturnType<typeof userEvent.setup>, text: string) {
  await user.type(screen.getByPlaceholderText(/what does the paper say/i), text);
  await waitFor(() => expect(screen.getByRole("button", { name: "Send" })).toBeEnabled());
  await user.click(screen.getByRole("button", { name: "Send" }));
}

const qaResponse: QAResponse = {
  question: "What is attention?",
  rewritten_question: "What is attention in Attention Survey?",
  answer: "Attention weighs token interactions.",
  conversation_id: "conv_1",
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

const emptyConversations: ConversationListResponse = {
  conversations: [],
  total: 0
};

beforeEach(() => {
  vi.clearAllMocks();
  localStorage.clear();
  vi.mocked(papersApi.getPapers).mockResolvedValue({
    count: 1,
    papers: [{ paper_id: "paper_001", title: "Attention Survey", abstract: "Abstract" }]
  });
  vi.mocked(conversationApi.listConversations).mockResolvedValue(emptyConversations);
  vi.mocked(conversationApi.getConversation).mockRejectedValue(new Error("not found"));
  vi.mocked(conversationApi.deleteConversation).mockResolvedValue({
    deleted: true,
    conversation_id: "conv_1"
  });
  vi.mocked(qaApi.askQuestion).mockResolvedValue(qaResponse);
});

describe("QaPage", () => {
  it("submits first QA request and stores returned conversation id", async () => {
    const user = userEvent.setup();
    renderPage();

    await screen.findByText("Attention Survey");
    await user.selectOptions(await screen.findByLabelText(/scope/i), "paper_001");
    await ask(user, "What is attention?");

    await waitFor(() => expect(screen.getByText("Attention weighs token interactions.")).toBeInTheDocument());
    expect(vi.mocked(qaApi.askQuestion).mock.calls[0][0]).toEqual({
      question: "What is attention?",
      paper_id: "paper_001",
      top_k: 5,
      conversation_id: null
    });
    expect(localStorage.getItem("research-agent:qa:conversation-id:v1")).toBe("conv_1");
    expect(screen.getByText(/rewritten query/i)).toBeInTheDocument();
  });

  it("sends follow-up questions with the active conversation id", async () => {
    const user = userEvent.setup();
    renderPage();

    await ask(user, "What is attention?");
    await waitFor(() => expect(screen.getByText("Attention weighs token interactions.")).toBeInTheDocument());

    vi.mocked(qaApi.askQuestion).mockResolvedValueOnce({
      ...qaResponse,
      question: "What about metrics?",
      rewritten_question: "What metrics does Attention Survey report?",
      answer: "It reports accuracy."
    });
    await ask(user, "What about metrics?");

    await waitFor(() => expect(screen.getByText("It reports accuracy.")).toBeInTheDocument());
    expect(vi.mocked(qaApi.askQuestion).mock.calls[1][0]).toMatchObject({
      question: "What about metrics?",
      conversation_id: "conv_1"
    });
  });

  it("loads a recent QA conversation and restores sources", async () => {
    const user = userEvent.setup();
    vi.mocked(conversationApi.listConversations).mockResolvedValue({
      total: 1,
      conversations: [
        {
          id: "conv_1",
          title: "Saved QA",
          created_at: 1,
          updated_at: 2,
          metadata: { kind: "qa" }
        }
      ]
    });
    const detail: ConversationDetail = {
      conversation: {
        id: "conv_1",
        title: "Saved QA",
        created_at: 1,
        updated_at: 2,
        metadata: { kind: "qa" }
      },
      messages: [
        {
          id: "m1",
          role: "user",
          content: "Saved question?",
          created_at: 1,
          metadata: { kind: "qa_user", paper_id: "paper_001", top_k: 7 }
        },
        {
          id: "m2",
          role: "assistant",
          content: "Saved answer.",
          created_at: 2,
          metadata: {
            kind: "qa_assistant",
            status: "done",
            rewritten_question: "Standalone saved question?",
            sources: qaResponse.sources
          }
        }
      ]
    };
    vi.mocked(conversationApi.getConversation).mockResolvedValue(detail);
    renderPage();

    await user.click(await screen.findByRole("button", { name: /Saved QA/i }));

    expect(await screen.findByText("Saved question?")).toBeInTheDocument();
    expect(screen.getByText("Saved answer.")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Sources (1)" }));
    expect(screen.getByText("Attention assigns weights.")).toBeInTheDocument();
    expect(screen.getByLabelText(/top k/i)).toHaveValue(7);
    expect(screen.getByLabelText(/scope/i)).toHaveValue("paper_001");
  });

  it("shows an error bubble when the QA request fails", async () => {
    const user = userEvent.setup();
    vi.mocked(qaApi.askQuestion).mockRejectedValue(new Error("LLM upstream is down"));
    renderPage();

    await ask(user, "What is attention?");

    expect(await screen.findByText("LLM upstream is down")).toBeInTheDocument();
    expect(screen.getByText("Error")).toBeInTheDocument();
  });

  it("starts a new chat without reusing the previous conversation id", async () => {
    const user = userEvent.setup();
    renderPage();

    await ask(user, "What is attention?");
    await waitFor(() => expect(screen.getByText("Attention weighs token interactions.")).toBeInTheDocument());

    await user.click(screen.getByRole("button", { name: "New chat" }));
    await ask(user, "Fresh question?");

    expect(vi.mocked(qaApi.askQuestion).mock.calls[1][0]).toMatchObject({
      question: "Fresh question?",
      conversation_id: null
    });
  });

  it("clears the active conversation through the backend", async () => {
    const user = userEvent.setup();
    renderPage();

    await ask(user, "What is attention?");
    await waitFor(() => expect(screen.getByText("Attention weighs token interactions.")).toBeInTheDocument());

    await user.click(screen.getByRole("button", { name: "Clear conversation" }));

    expect(vi.mocked(conversationApi.deleteConversation).mock.calls[0][0]).toBe("conv_1");
    await waitFor(() => expect(screen.queryByText("Attention weighs token interactions.")).not.toBeInTheDocument());
    expect(localStorage.getItem("research-agent:qa:conversation-id:v1")).toBeNull();
  });

  it("shows a thinking message while pending", async () => {
    const user = userEvent.setup();
    const pending = deferred<QAResponse>();
    vi.mocked(qaApi.askQuestion).mockReturnValue(pending.promise);
    renderPage();

    await ask(user, "What is attention?");

    expect(screen.getByText("What is attention?")).toBeInTheDocument();
    expect(screen.getByText(/model is retrieving sources/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Thinking" })).toBeDisabled();

    pending.resolve(qaResponse);
    await waitFor(() => expect(screen.getByText("Attention weighs token interactions.")).toBeInTheDocument());
  });

  it("renders an inline error when the conversations list fails to load", async () => {
    vi.mocked(conversationApi.listConversations).mockRejectedValue(
      new Error("network down")
    );
    renderPage();

    expect(await screen.findByText("Unable to load conversations")).toBeInTheDocument();
    expect(screen.getByText("network down")).toBeInTheDocument();
  });

  it("paginates the conversation list via Show more", async () => {
    const user = userEvent.setup();
    const makeConv = (i: number) => ({
      id: `conv_${i}`,
      title: `Thread ${i}`,
      created_at: 1,
      updated_at: 2,
      metadata: { kind: "qa" }
    });
    const all = Array.from({ length: 12 }, (_, i) => makeConv(i));
    vi.mocked(conversationApi.listConversations).mockImplementation(
      (_kind?: string, limit = 8) =>
        Promise.resolve({ total: all.length, conversations: all.slice(0, limit) })
    );
    renderPage();

    // First page: 8 chips + a "Show more (4)" button.
    expect(await screen.findByRole("button", { name: "Thread 0" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Thread 11" })).not.toBeInTheDocument();
    const showMore = screen.getByRole("button", { name: /Show more \(4\)/ });

    await user.click(showMore);

    // Second page: all 12 chips, no more "Show more".
    expect(await screen.findByRole("button", { name: "Thread 11" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Show more/ })).not.toBeInTheDocument();
    expect(vi.mocked(conversationApi.listConversations).mock.calls.map((c) => c[1])).toContain(16);
  });

  it("shows an error banner when deleting a conversation fails with a server error", async () => {
    const user = userEvent.setup();
    renderPage();

    await ask(user, "What is attention?");
    await waitFor(() => expect(screen.getByText("Attention weighs token interactions.")).toBeInTheDocument());

    vi.mocked(conversationApi.deleteConversation).mockRejectedValue(
      new ApiError("server error", 500)
    );

    await user.click(screen.getByRole("button", { name: "Clear conversation" }));

    expect(await screen.findByText("Failed to clear conversation")).toBeInTheDocument();
    expect(screen.getByText("server error")).toBeInTheDocument();
    // Active conversation is preserved on non-404 failure (still exists server-side).
    expect(localStorage.getItem("research-agent:qa:conversation-id:v1")).toBe("conv_1");
  });

  it("clears local state when delete fails with 404 (already deleted server-side)", async () => {
    const user = userEvent.setup();
    renderPage();

    await ask(user, "What is attention?");
    await waitFor(() => expect(screen.getByText("Attention weighs token interactions.")).toBeInTheDocument());

    vi.mocked(conversationApi.deleteConversation).mockRejectedValue(
      new ApiError("not found", 404)
    );

    await user.click(screen.getByRole("button", { name: "Clear conversation" }));

    await waitFor(() => expect(screen.queryByText("Attention weighs token interactions.")).not.toBeInTheDocument());
    expect(localStorage.getItem("research-agent:qa:conversation-id:v1")).toBeNull();
    // No error banner for 404 — treated as already-deleted.
    expect(screen.queryByText("Failed to clear conversation")).not.toBeInTheDocument();
  });
});
