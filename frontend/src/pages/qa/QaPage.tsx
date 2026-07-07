import { FormEvent, useEffect, useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { SendHorizontal, X } from "lucide-react";
import { askQuestion } from "../../api/qa";
import { deleteConversation, getConversation, listConversations } from "../../api/conversations";
import { getPapers } from "../../api/papers";
import { ApiError } from "../../api/client";
import type { ConversationDetail, ConversationMessage, SourceItem } from "../../api/types";
import { EmptyState } from "../../components/empty-state/EmptyState";
import { ErrorState } from "../../components/error-state/ErrorState";
import { PaperSelector } from "../../components/papers/PaperSelector";
import { MarkdownContent } from "../../components/common/MarkdownContent";

const QA_CONVERSATION_ID_KEY = "research-agent:qa:conversation-id:v1";
const MAX_VISIBLE_MESSAGES = 30;

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
      rewritten_question?: string | null;
      error?: string;
      request: {
        question: string;
        paper_id: string | null;
        top_k: number;
      };
    };

function createMessageId(prefix: string) {
  if (typeof crypto !== "undefined" && "randomUUID" in crypto) {
    return `${prefix}_${crypto.randomUUID()}`;
  }
  return `${prefix}_${Date.now()}_${Math.random().toString(36).slice(2)}`;
}

function loadStoredConversationId() {
  try {
    return localStorage.getItem(QA_CONVERSATION_ID_KEY);
  } catch {
    return null;
  }
}

function storeConversationId(conversationId: string | null) {
  try {
    if (conversationId) {
      localStorage.setItem(QA_CONVERSATION_ID_KEY, conversationId);
    } else {
      localStorage.removeItem(QA_CONVERSATION_ID_KEY);
    }
  } catch {
    // Browser storage is a convenience cache only.
  }
}

function stringMetadataValue(metadata: Record<string, unknown>, key: string) {
  const value = metadata[key];
  return typeof value === "string" ? value : null;
}

function numberMetadataValue(metadata: Record<string, unknown>, key: string, fallback: number) {
  const value = metadata[key];
  return typeof value === "number" ? value : fallback;
}

function sourcesMetadataValue(metadata: Record<string, unknown>) {
  const value = metadata.sources;
  return Array.isArray(value) ? (value as SourceItem[]) : [];
}

function mapConversationMessage(message: ConversationMessage): QaMessage | null {
  const createdAt = new Date(message.created_at * 1000).toISOString();
  if (message.role === "user") {
    return {
      id: message.id,
      role: "user",
      content: message.content,
      created_at: createdAt,
      paper_id: stringMetadataValue(message.metadata, "paper_id"),
      top_k: numberMetadataValue(message.metadata, "top_k", 5)
    };
  }

  if (message.role === "assistant") {
    const status = stringMetadataValue(message.metadata, "status") === "error" ? "error" : "done";
    return {
      id: message.id,
      role: "assistant",
      content: message.content,
      status,
      created_at: createdAt,
      sources: sourcesMetadataValue(message.metadata),
      rewritten_question: stringMetadataValue(message.metadata, "rewritten_question"),
      error: stringMetadataValue(message.metadata, "error") ?? undefined,
      request: {
        question: stringMetadataValue(message.metadata, "rewritten_question") ?? message.content,
        paper_id: stringMetadataValue(message.metadata, "paper_id"),
        top_k: numberMetadataValue(message.metadata, "top_k", 5)
      }
    };
  }

  return null;
}

function mapConversationDetail(detail: ConversationDetail) {
  return detail.messages
    .map(mapConversationMessage)
    .filter((message): message is QaMessage => message !== null)
    .slice(-MAX_VISIBLE_MESSAGES);
}

export function QaPage() {
  const queryClient = useQueryClient();
  const skipNextConversationLoad = useRef(false);
  const [question, setQuestion] = useState("");
  const [activeConversationId, setActiveConversationId] = useState<string | null>(() => loadStoredConversationId());
  const [paperId, setPaperId] = useState("");
  const [topK, setTopK] = useState(5);
  const [messages, setMessages] = useState<QaMessage[]>([]);
  const [sourcePanel, setSourcePanel] = useState<{
    title: string;
    sources: SourceItem[];
  } | null>(null);
  const [deleteError, setDeleteError] = useState<string | null>(null);

  const papersQuery = useQuery({
    queryKey: ["papers"],
    queryFn: getPapers
  });

  const conversationsQuery = useQuery({
    queryKey: ["qa-conversations"],
    queryFn: () => listConversations("qa", 8)
  });

  const qaMutation = useMutation({
    mutationFn: askQuestion
  });

  const deleteMutation = useMutation({
    mutationFn: deleteConversation,
    onMutate: () => {
      setDeleteError(null);
    },
    onSuccess: () => {
      setActiveConversationId(null);
      setMessages([]);
      setSourcePanel(null);
      queryClient.invalidateQueries({ queryKey: ["qa-conversations"] });
    },
    onError: (error) => {
      // 404 = already deleted server-side; mirror success so the UI clears.
      if (error instanceof ApiError && error.status === 404) {
        setActiveConversationId(null);
        setMessages([]);
        setSourcePanel(null);
      } else {
        setDeleteError(error instanceof Error ? error.message : "Failed to clear conversation");
      }
      queryClient.invalidateQueries({ queryKey: ["qa-conversations"] });
    }
  });

  useEffect(() => {
    if (!activeConversationId) return;
    if (skipNextConversationLoad.current) {
      skipNextConversationLoad.current = false;
      return;
    }
    let cancelled = false;
    getConversation(activeConversationId)
      .then((detail) => {
        if (cancelled) return;
        setMessages(mapConversationDetail(detail));
        const lastUser = [...detail.messages].reverse().find((message) => message.role === "user");
        if (lastUser) {
          const paper = stringMetadataValue(lastUser.metadata, "paper_id");
          const restoredTopK = numberMetadataValue(lastUser.metadata, "top_k", 5);
          setPaperId(paper ?? "");
          setTopK(restoredTopK);
        }
      })
      .catch(() => {
        if (cancelled) return;
        setActiveConversationId(null);
        setMessages([]);
      });
    return () => {
      cancelled = true;
    };
  }, [activeConversationId]);

  useEffect(() => {
    storeConversationId(activeConversationId);
  }, [activeConversationId]);

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

    setMessages((current) => [...current, userMessage, assistantMessage].slice(-MAX_VISIBLE_MESSAGES));
    setQuestion("");
    qaMutation.mutate(
      {
        question: trimmedQuestion,
        paper_id: scopePaperId,
        top_k: scopeTopK,
        conversation_id: activeConversationId
      },
      {
        onSuccess: (result) => {
          if (result.conversation_id) {
            skipNextConversationLoad.current = result.conversation_id !== activeConversationId;
            setActiveConversationId(result.conversation_id);
          }
          queryClient.invalidateQueries({ queryKey: ["qa-conversations"] });
          setMessages((current) =>
            current.map((message) =>
              message.id === assistantMessageId && message.role === "assistant"
                ? {
                    ...message,
                    content: result.answer,
                    status: "done",
                    sources: result.sources,
                    rewritten_question: result.rewritten_question,
                    request: {
                      ...message.request,
                      question: result.question
                    }
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

  const startNewChat = () => {
    skipNextConversationLoad.current = false;
    setActiveConversationId(null);
    setMessages([]);
    setSourcePanel(null);
  };

  const clearConversation = () => {
    if (activeConversationId) {
      deleteMutation.mutate(activeConversationId);
      return;
    }
    startNewChat();
  };

  const loadConversation = (conversationId: string) => {
    skipNextConversationLoad.current = false;
    setActiveConversationId(conversationId);
    setSourcePanel(null);
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
        <div className="flex flex-wrap gap-2">
          <button
            type="button"
            onClick={startNewChat}
            disabled={qaMutation.isPending}
            className="rounded-md border border-line bg-panel px-3 py-2 text-sm font-medium text-muted hover:bg-surface hover:text-ink disabled:opacity-60"
          >
            New chat
          </button>
          <button
            type="button"
            onClick={clearConversation}
            disabled={!hasMessages || qaMutation.isPending || deleteMutation.isPending}
            className="rounded-md border border-line bg-panel px-3 py-2 text-sm font-medium text-muted hover:bg-surface hover:text-ink disabled:opacity-60"
          >
            Clear conversation
          </button>
        </div>
      </section>

      {conversationsQuery.error ? (
        <ErrorState
          title="Unable to load conversations"
          message={(conversationsQuery.error as Error).message}
        />
      ) : conversationsQuery.data?.conversations.length ? (
        <section className="flex flex-wrap gap-2">
          {conversationsQuery.data.conversations.map((conversation) => (
            <button
              key={conversation.id}
              type="button"
              onClick={() => loadConversation(conversation.id)}
              className={`rounded-full border px-3 py-1.5 text-xs font-medium ${
                conversation.id === activeConversationId
                  ? "border-accent bg-accent text-white"
                  : "border-line bg-panel text-muted hover:bg-surface hover:text-ink"
              }`}
            >
              {conversation.title || "QA conversation"}
            </button>
          ))}
        </section>
      ) : null}

      {deleteError ? (
        <ErrorState title="Failed to clear conversation" message={deleteError} />
      ) : null}

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
                    <>
                      <MarkdownContent content={message.content} className="mt-3" />
                      {message.rewritten_question && (
                        <details className="mt-4 rounded-md border border-line bg-surface px-3 py-2 text-xs text-muted">
                          <summary className="cursor-pointer font-medium text-ink">Rewritten query</summary>
                          <p className="mt-2 whitespace-pre-wrap">{message.rewritten_question}</p>
                        </details>
                      )}
                    </>
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
