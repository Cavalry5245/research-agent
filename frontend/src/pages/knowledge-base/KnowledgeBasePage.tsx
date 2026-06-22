import { FormEvent, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Plus, X } from "lucide-react";
import {
  addPaperToKnowledgeBase,
  createKnowledgeBase,
  getKnowledgeBases,
  removePaperFromKnowledgeBase
} from "../../api/knowledgeBase";
import { getPapers } from "../../api/papers";
import { EmptyState } from "../../components/empty-state/EmptyState";
import { ErrorState } from "../../components/error-state/ErrorState";
import { PaperSelector } from "../../components/papers/PaperSelector";

export function KnowledgeBasePage() {
  const queryClient = useQueryClient();
  const [kbId, setKbId] = useState("");
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [selectedPapers, setSelectedPapers] = useState<Record<string, string>>({});

  const kbQuery = useQuery({
    queryKey: ["knowledge-bases"],
    queryFn: getKnowledgeBases
  });

  const papersQuery = useQuery({
    queryKey: ["papers"],
    queryFn: getPapers
  });

  const refresh = () => void queryClient.invalidateQueries({ queryKey: ["knowledge-bases"] });

  const createMutation = useMutation({
    mutationFn: createKnowledgeBase,
    onSuccess: () => {
      setKbId("");
      setName("");
      setDescription("");
      refresh();
    }
  });

  const addMutation = useMutation({
    mutationFn: ({ targetKbId, paperId }: { targetKbId: string; paperId: string }) => addPaperToKnowledgeBase(targetKbId, paperId),
    onSuccess: refresh
  });

  const removeMutation = useMutation({
    mutationFn: ({ targetKbId, paperId }: { targetKbId: string; paperId: string }) => removePaperFromKnowledgeBase(targetKbId, paperId),
    onSuccess: refresh
  });

  const handleCreate = (event: FormEvent) => {
    event.preventDefault();
    if (!kbId.trim() || !name.trim()) return;
    createMutation.mutate({ kb_id: kbId.trim(), name: name.trim(), description: description.trim() });
  };

  if (kbQuery.isLoading || papersQuery.isLoading) {
    return <p className="text-sm text-muted">Loading knowledge bases...</p>;
  }

  if (kbQuery.error) {
    return <ErrorState title="Unable to load knowledge bases" message={(kbQuery.error as Error).message} />;
  }

  if (papersQuery.error) {
    return <ErrorState title="Unable to load papers" message={(papersQuery.error as Error).message} />;
  }

  const knowledgeBases = kbQuery.data?.knowledge_bases ?? [];
  const papers = papersQuery.data?.papers ?? [];

  return (
    <div className="space-y-6">
      <section>
        <h1 className="text-2xl font-semibold text-ink">Knowledge Base</h1>
        <p className="mt-2 max-w-3xl text-sm leading-6 text-muted">
          Create focused paper sets and manage paper membership.
        </p>
      </section>

      <form onSubmit={handleCreate} className="grid gap-3 rounded-md border border-line bg-panel p-4 shadow-panel md:grid-cols-[12rem_1fr_1.4fr_auto] md:items-end">
        <label className="block">
          <span className="text-xs font-medium uppercase text-muted">KB ID</span>
          <input value={kbId} onChange={(event) => setKbId(event.target.value)} className="mt-1 w-full rounded-md border border-line px-3 py-2 text-sm" />
        </label>
        <label className="block">
          <span className="text-xs font-medium uppercase text-muted">Name</span>
          <input value={name} onChange={(event) => setName(event.target.value)} className="mt-1 w-full rounded-md border border-line px-3 py-2 text-sm" />
        </label>
        <label className="block">
          <span className="text-xs font-medium uppercase text-muted">Description</span>
          <input value={description} onChange={(event) => setDescription(event.target.value)} className="mt-1 w-full rounded-md border border-line px-3 py-2 text-sm" />
        </label>
        <button
          type="submit"
          disabled={!kbId.trim() || !name.trim() || createMutation.isPending}
          className="inline-flex items-center justify-center gap-2 rounded-md bg-accent px-4 py-2 text-sm font-medium text-white hover:bg-accent-hover disabled:opacity-60"
        >
          <Plus className="h-4 w-4" aria-hidden="true" />
          Create
        </button>
      </form>

      {(createMutation.error || addMutation.error || removeMutation.error) && (
        <ErrorState
          title="Knowledge base action failed"
          message={((createMutation.error || addMutation.error || removeMutation.error) as Error).message}
        />
      )}

      {knowledgeBases.length === 0 ? (
        <EmptyState title="No knowledge bases" description="Create a knowledge base to group papers for focused retrieval." />
      ) : (
        <section className="grid gap-4 xl:grid-cols-2">
          {knowledgeBases.map((kb) => (
            <article key={kb.id} className="rounded-md border border-line bg-panel p-4 shadow-panel">
              <div className="flex items-start justify-between gap-4">
                <div>
                  <h2 className="text-sm font-semibold text-ink">{kb.name}</h2>
                  <p className="mt-1 text-xs text-muted">{kb.id}</p>
                  {kb.description && <p className="mt-2 text-sm text-muted">{kb.description}</p>}
                </div>
                <span className="rounded-full bg-surface px-2 py-1 text-xs font-medium text-muted">{kb.paper_ids.length} papers</span>
              </div>

              <div className="mt-4 flex gap-2">
                <div className="flex-1">
                  <PaperSelector
                    papers={papers}
                    value={selectedPapers[kb.id] ?? ""}
                    onChange={(paperId) => setSelectedPapers((current) => ({ ...current, [kb.id]: paperId }))}
                    label="Add paper"
                  />
                </div>
                <button
                  type="button"
                  disabled={!selectedPapers[kb.id] || addMutation.isPending}
                  onClick={() => addMutation.mutate({ targetKbId: kb.id, paperId: selectedPapers[kb.id] })}
                  className="self-end rounded-md border border-line px-3 py-2 text-sm font-medium text-muted hover:bg-surface disabled:opacity-60"
                >
                  Add
                </button>
              </div>

              <div className="mt-4 space-y-2">
                {kb.paper_ids.length === 0 ? (
                  <p className="text-sm text-muted">No papers assigned.</p>
                ) : (
                  kb.paper_ids.map((paperId) => (
                    <div key={paperId} className="flex items-center justify-between gap-3 rounded-md border border-line bg-surface px-3 py-2">
                      <span className="text-sm text-ink">{paperId}</span>
                      <button
                        type="button"
                        onClick={() => removeMutation.mutate({ targetKbId: kb.id, paperId })}
                        className="inline-flex h-7 w-7 items-center justify-center rounded border border-line text-muted hover:border-red-200 hover:bg-red-50 hover:text-red-600"
                        aria-label={`Remove ${paperId} from ${kb.id}`}
                      >
                        <X className="h-4 w-4" aria-hidden="true" />
                      </button>
                    </div>
                  ))
                )}
              </div>
            </article>
          ))}
        </section>
      )}
    </div>
  );
}
