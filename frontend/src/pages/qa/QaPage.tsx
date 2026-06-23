import { FormEvent, useEffect, useMemo, useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { SendHorizontal, X } from "lucide-react";
import { askQuestion } from "../../api/qa";
import { getPapers } from "../../api/papers";
import type { SourceItem } from "../../api/types";
import { EmptyState } from "../../components/empty-state/EmptyState";
import { ErrorState } from "../../components/error-state/ErrorState";
import { PaperSelector } from "../../components/papers/PaperSelector";
import { MarkdownContent } from "../../components/common/MarkdownContent";

const QA_STORAGE_KEY = "research-agent:qa:conversation:v1";
const MAX_STORED_MESSAGES = 30;

type QaMessage =
  | {
      id: string;
      role: "user";
      content: string;
      created_at: string;
      paper_id: string | null;
      top_k: number;
    }
  | {
      id: string;
      role: "assistant";
      content: string;
      status: "thinking" | "done" | "error";
      created_at: string;
      sources: SourceItem[];
      error?: string;
      request: {
        question: string;
        paper_id: string | null;
        top_k: number;
      };
    };

interface StoredQaState {
  messages: QaMessage[];
  paperId: string;
  topK: number;
}

function createMessageId(prefix: string) {
  if (typeof crypto !== "undefined" && "randomUUID" in crypto) {
    return `${prefix}_${crypto.randomUUID()}`;
  }
  return `${prefix}_${Date.now()}_${Math.random().toString(36).slice(2)}`;
}

function loadStoredQaState(): StoredQaState | null {
  try {
    const raw = localStorage.getItem(QA_STORAGE_KEY);
    return raw ? (JSON.parse(raw) as StoredQaState) : null;
  } catch {
    return null;
  }
}

export function QaPage() {
  const storedState = useMemo(() => loadStoredQaState(), []);
  const [question, setQuestion] = useState("");
  const [paperId, setPaperId] = useState(storedState?.paperId ?? "");
  const [topK, setTopK] = useState(storedState?.topK ?? 5);
  const [messages, setMessages] = useState<QaMessage[]>(storedState?.messages ?? []);
  const [sourcePanel, setSourcePanel] = useState<{
    title: string;
    sources: SourceItem[];
  } | null>(null);

  const papersQuery = useQuery({
    queryKey: ["papers"],
    queryFn: getPapers
  });

  const qaMutation = useMutation({
    mutationFn: askQuestion
  });

  useEffect(() => {
    if (messages.length === 0) {
      localStorage.removeItem(QA_STORAGE_KEY);
      return;
    }

    const payload: StoredQaState = {
      messages: messages.slice(-MAX_STORED_MESSAGES),
      paperId,
      topK
    };
    localStorage.setItem(QA_STORAGE_KEY, JSON.stringify(payload));
  }, [messages, paperId, topK]);

  const submitQuestion = (content: string, scopePaperId: string | null, scopeTopK: number) => {
    const trimmedQuestion = content.trim();
    if (!trimmedQuestion || qaMutation.isPending) return;

    const userMessage: QaMessage = {
      id: createMessageId("user"),
      role: "user",
      content: trimmedQuestion,
      created_at: new Date().toISOString(),
      paper_id: scopePaperId,
      top_k: scopeTopK
    };
    const assistantMessageId = createMessageId("assistant");
    const assistantMessage: QaMessage = {
      id: assistantMessageId,
      role: "assistant",
      content: "Thinking...",
      status: "thinking",
      created_at: new Date().toISOString(),
      sources: [],
      request: {
        question: trimmedQuestion,
        paper_id: scopePaperId,
        top_k: scopeTopK
      }
    };

    setMessages((current) => [...current, userMessage, assistantMessage].slice(-MAX_STORED_MESSAGES));
    setQuestion("");
    qaMutation.mutate(
      {
        question: trimmedQuestion,
        paper_id: scopePaperId,
        top_k: scopeTopK
      },
      {
        onSuccess: (result) => {
          setMessages((current) =>
            current.map((message) =>
              message.id === assistantMessageId && message.role === "assistant"
                ? {
                    ...message,
                    content: result.answer,
                    status: "done",
                    sources: result.sources
                  }
                : message
            )
          );
        },
        onError: (error) => {
          setMessages((current) =>
            current.map((message) =>
              message.id === assistantMessageId && message.role === "assistant"
                ? {
                    ...message,
                    content: error instanceof Error ? error.message : "QA failed",
                    status: "error",
                    error: error instanceof Error ? error.message : "QA failed",
                    sources: []
                  }
                : message
            )
          );
        }
      }
    );
  };

  const handleSubmit = (event: FormEvent) => {
    event.preventDefault();
    submitQuestion(question, paperId || null, topK);
  };

  const clearConversation = () => {
    setMessages([]);
    setSourcePanel(null);
    localStorage.removeItem(QA_STORAGE_KEY);
  };

  if (papersQuery.error) {
    return <ErrorState title="Unable to load papers" message={(papersQuery.error as Error).message} />;
  }

  const papers = papersQuery.data?.papers ?? [];
  const hasMessages = messages.length > 0;

  return (
    <div className="flex min-h-[calc(100vh-8rem)] flex-col gap-6">
      <section className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-ink">QA</h1>
          <p className="mt-2 max-w-3xl text-sm leading-6 text-muted">
            Ask questions against the indexed library or scope retrieval to one paper.
          </p>
        </div>
        <button
          type="button"
          onClick={clearConversation}
          disabled={!hasMessages || qaMutation.isPending}
          className="rounded-md border border-line bg-panel px-3 py-2 text-sm font-medium text-muted hover:bg-surface hover:text-ink disabled:opacity-60"
        >
          Clear conversation
        </button>
      </section>

      <div className="flex flex-1 flex-col gap-4 xl:flex-row xl:items-start">
        {hasMessages ? (
          <section className="min-w-0 flex-1 space-y-4 pb-2">
            {messages.map((message) =>
              message.role === "user" ? (
                <article key={message.id} className="ml-auto max-w-3xl rounded-md bg-accent px-4 py-3 text-white shadow-panel">
                  <p className="whitespace-pre-wrap text-sm leading-6">{message.content}</p>
                  <p className="mt-2 text-xs text-blue-100">
                    Scope {message.paper_id || "Library"} - top {message.top_k}
                  </p>
                </article>
              ) : (
                <article key={message.id} className="max-w-4xl rounded-md border border-line bg-panel p-4 shadow-panel">
                  <div className="flex flex-wrap items-center gap-2">
                    <p className="text-xs font-medium uppercase text-muted">
                      {message.status === "thinking" ? "Thinking" : message.status === "error" ? "Error" : "Answer"}
                    </p>
                    {message.status === "thinking" && (
                      <span className="h-2 w-2 animate-pulse rounded-full bg-accent" aria-hidden="true" />
                    )}
                  </div>
                  {message.status === "error" ? (
                    <p className="mt-3 rounded-md bg-red-50 p-3 text-sm text-red-700">{message.error || message.content}</p>
                  ) : message.status === "thinking" ? (
                    <p className="mt-3 text-sm text-muted">The model is retrieving sources and composing an answer...</p>
                  ) : (
                    <MarkdownContent content={message.content} className="mt-3" />
                  )}

                  {message.status === "done" && (
                    <button
                      type="button"
                      onClick={() =>
                        setSourcePanel({
                          title: message.request.question,
                          sources: message.sources
                        })
                      }
                      className="mt-4 rounded-full border border-line px-3 py-1.5 text-xs font-medium text-muted hover:bg-surface hover:text-ink"
                    >
                      Sources ({message.sources.length})
                    </button>
                  )}
                </article>
              )
            )}
          </section>
        ) : (
          <div className="flex items-center">
            <EmptyState title="No answer yet" description="Ask a question to see the generated answer and source chunks." />
          </div>
        )}

        {sourcePanel && (
          <aside className="flex max-h-[calc(100vh-18rem)] min-h-96 w-full shrink-0 flex-col rounded-md border border-line bg-panel shadow-panel xl:sticky xl:top-4 xl:w-96">
            <div className="flex items-start justify-between gap-3 border-b border-line p-4">
              <div>
                <h2 className="text-base font-semibold text-ink">Sources</h2>
                <p className="mt-1 line-clamp-2 text-xs text-muted">{sourcePanel.title}</p>
              </div>
              <button
                type="button"
                onClick={() => setSourcePanel(null)}
                className="inline-flex h-8 w-8 items-center justify-center rounded-full border border-line text-muted hover:bg-surface hover:text-ink"
                aria-label="Close sources"
              >
                <X className="h-4 w-4" aria-hidden="true" />
              </button>
            </div>
            <div className="flex-1 overflow-y-auto p-4">
              {sourcePanel.sources.length === 0 ? (
                <EmptyState title="No sources returned" description="The backend answered without citation chunks." />
              ) : (
                <div className="space-y-3">
                  {sourcePanel.sources.map((source) => (
                    <article key={source.chunk_id} className="rounded-md border border-line bg-surface p-3">
                      <div className="flex flex-wrap items-center gap-2 text-xs text-muted">
                        <span className="font-medium text-ink">{source.title}</span>
                        <span>{source.section}</span>
                        {source.score !== null && source.score !== undefined && <span>score {source.score.toFixed(3)}</span>}
                      </div>
                      <p className="mt-2 text-sm leading-6 text-ink">{source.content}</p>
                    </article>
                  ))}
                </div>
              )}
            </div>
          </aside>
        )}
      </div>

      <form
        onSubmit={handleSubmit}
        className="sticky bottom-0 z-20 mx-auto w-full max-w-5xl rounded-[1.75rem] border border-line bg-panel/95 p-3 shadow-panel backdrop-blur"
      >
        <label className="block">
          <span className="sr-only">Question</span>
          <textarea
            value={question}
            onChange={(event) => setQuestion(event.target.value)}
            rows={3}
            placeholder="What does the paper say about retrieval quality?"
            className="max-h-48 min-h-24 w-full resize-y rounded-[1.25rem] border-0 bg-transparent px-4 py-3 text-sm leading-6 text-ink outline-none placeholder:text-muted focus:ring-0"
          />
        </label>
        <div className="flex flex-col gap-2 border-t border-line px-2 pt-3 sm:flex-row sm:items-end sm:justify-between">
          <div className="grid flex-1 gap-2 sm:grid-cols-[minmax(0,1fr)_6rem]">
            <PaperSelector papers={papers} value={paperId} onChange={setPaperId} label="Scope" />
            <label className="block">
              <span className="text-xs font-medium uppercase text-muted">Top K</span>
              <input
                type="number"
                min={1}
                max={20}
                value={topK}
                onChange={(event) => setTopK(Number(event.target.value))}
                className="mt-1 w-full rounded-full border border-line bg-surface px-3 py-2 text-sm text-ink"
              />
            </label>
          </div>
          <button
            type="submit"
            disabled={!question.trim() || qaMutation.isPending}
            className="inline-flex h-11 w-11 shrink-0 items-center justify-center rounded-full bg-accent text-white shadow-sm transition hover:bg-accent-hover disabled:cursor-not-allowed disabled:opacity-50"
            aria-label={qaMutation.isPending ? "Thinking" : "Send"}
            title={qaMutation.isPending ? "Thinking" : "Send"}
          >
            {qaMutation.isPending ? (
              <span className="h-2.5 w-2.5 animate-pulse rounded-full bg-white" aria-hidden="true" />
            ) : (
              <SendHorizontal className="h-5 w-5" aria-hidden="true" />
            )}
          </button>
        </div>
      </form>

    </div>
  );
}
