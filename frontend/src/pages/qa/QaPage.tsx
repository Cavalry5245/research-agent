import { FormEvent, useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { askQuestion } from "../../api/qa";
import { getPapers } from "../../api/papers";
import { EmptyState } from "../../components/empty-state/EmptyState";
import { ErrorState } from "../../components/error-state/ErrorState";
import { PaperSelector } from "../../components/papers/PaperSelector";

export function QaPage() {
  const [question, setQuestion] = useState("");
  const [paperId, setPaperId] = useState("");
  const [topK, setTopK] = useState(5);

  const papersQuery = useQuery({
    queryKey: ["papers"],
    queryFn: getPapers
  });

  const qaMutation = useMutation({
    mutationFn: askQuestion
  });

  const handleSubmit = (event: FormEvent) => {
    event.preventDefault();
    if (!question.trim()) return;
    qaMutation.mutate({
      question: question.trim(),
      paper_id: paperId || null,
      top_k: topK
    });
  };

  if (papersQuery.error) {
    return <ErrorState title="Unable to load papers" message={(papersQuery.error as Error).message} />;
  }

  const papers = papersQuery.data?.papers ?? [];

  return (
    <div className="space-y-6">
      <section>
        <h1 className="text-2xl font-semibold text-ink">QA</h1>
        <p className="mt-2 max-w-3xl text-sm leading-6 text-muted">
          Ask questions against the indexed library or scope retrieval to one paper.
        </p>
      </section>

      <form onSubmit={handleSubmit} className="grid gap-4 rounded-md border border-line bg-panel p-4 shadow-panel xl:grid-cols-[1fr_18rem]">
        <label className="block">
          <span className="text-xs font-medium uppercase text-muted">Question</span>
          <textarea
            value={question}
            onChange={(event) => setQuestion(event.target.value)}
            rows={5}
            placeholder="What does the paper say about retrieval quality?"
            className="mt-1 w-full resize-y rounded-md border border-line bg-panel px-3 py-2 text-sm text-ink"
          />
        </label>
        <div className="space-y-3">
          <PaperSelector papers={papers} value={paperId} onChange={setPaperId} label="Scope" />
          <label className="block">
            <span className="text-xs font-medium uppercase text-muted">Top K</span>
            <input
              type="number"
              min={1}
              max={20}
              value={topK}
              onChange={(event) => setTopK(Number(event.target.value))}
              className="mt-1 w-full rounded-md border border-line bg-panel px-3 py-2 text-sm text-ink"
            />
          </label>
          <button
            type="submit"
            disabled={!question.trim() || qaMutation.isPending}
            className="w-full rounded-md bg-accent px-4 py-2 text-sm font-medium text-white hover:bg-accent-hover disabled:opacity-60"
          >
            {qaMutation.isPending ? "Asking" : "Ask"}
          </button>
        </div>
      </form>

      {qaMutation.error && <ErrorState title="QA failed" message={(qaMutation.error as Error).message} />}

      {qaMutation.data ? (
        <section className="space-y-4">
          <div className="rounded-md border border-line bg-panel p-4 shadow-panel">
            <p className="text-xs font-medium uppercase text-muted">Answer</p>
            <p className="mt-3 whitespace-pre-wrap text-sm leading-6 text-ink">{qaMutation.data.answer}</p>
          </div>
          <div className="rounded-md border border-line bg-panel p-4 shadow-panel">
            <h2 className="text-sm font-semibold text-ink">Sources</h2>
            {qaMutation.data.sources.length === 0 ? (
              <div className="mt-4">
                <EmptyState title="No sources returned" description="The backend answered without citation chunks." />
              </div>
            ) : (
              <div className="mt-4 space-y-3">
                {qaMutation.data.sources.map((source) => (
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
        </section>
      ) : (
        <EmptyState title="No answer yet" description="Ask a question to see the generated answer and source chunks." />
      )}
    </div>
  );
}
