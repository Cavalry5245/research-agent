import { FormEvent, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { GitCompare, MessageSquare, Plus, Workflow, X } from "lucide-react";
import {
  addPapersToKnowledgeBase,
  createKnowledgeBase,
  getKnowledgeBases,
  removePaperFromKnowledgeBase
} from "../../api/knowledgeBase";
import { getPapers } from "../../api/papers";
import { EmptyState } from "../../components/empty-state/EmptyState";
import { ErrorState } from "../../components/error-state/ErrorState";
import { ResearchSetPaperPicker } from "./ResearchSetPaperPicker";
import { formatUpdatedAt, getAvailablePapers, getMemberPapers, percent } from "./researchSetUtils";

export function KnowledgeBasePage() {
  const queryClient = useQueryClient();
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [selectedPaperIds, setSelectedPaperIds] = useState<Record<string, string[]>>({});

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
      setName("");
      setDescription("");
      refresh();
    }
  });

  const addMutation = useMutation({
    mutationFn: ({ targetKbId, paperIds }: { targetKbId: string; paperIds: string[] }) => addPapersToKnowledgeBase(targetKbId, paperIds),
    onSuccess: (_data, variables) => {
      setSelectedPaperIds((current) => ({ ...current, [variables.targetKbId]: [] }));
      refresh();
    }
  });

  const removeMutation = useMutation({
    mutationFn: ({ targetKbId, paperId }: { targetKbId: string; paperId: string }) => removePaperFromKnowledgeBase(targetKbId, paperId),
    onSuccess: refresh
  });

  const handleCreate = (event: FormEvent) => {
    event.preventDefault();
    if (!name.trim()) return;
    createMutation.mutate({ name: name.trim(), description: description.trim() });
  };

  const toggleSelectedPaper = (kbId: string, paperId: string) => {
    setSelectedPaperIds((current) => {
      const selected = new Set(current[kbId] ?? []);
      if (selected.has(paperId)) {
        selected.delete(paperId);
      } else {
        selected.add(paperId);
      }
      return { ...current, [kbId]: Array.from(selected) };
    });
  };

  if (kbQuery.isLoading || papersQuery.isLoading) {
    return <p className="text-sm text-muted">Loading research sets...</p>;
  }

  if (kbQuery.error) {
    return <ErrorState title="Unable to load research sets" message={(kbQuery.error as Error).message} />;
  }

  if (papersQuery.error) {
    return <ErrorState title="Unable to load papers" message={(papersQuery.error as Error).message} />;
  }

  const knowledgeBases = kbQuery.data?.knowledge_bases ?? [];
  const papers = papersQuery.data?.papers ?? [];

  return (
    <div className="space-y-6">
      <section>
        <h1 className="text-2xl font-semibold text-ink">Research Sets</h1>
        <p className="mt-2 max-w-3xl text-sm leading-6 text-muted">
          Group papers into reusable sets for QA, comparison, and workflow runs.
        </p>
      </section>

      <form onSubmit={handleCreate} className="grid gap-3 rounded-md border border-line bg-panel p-4 shadow-panel md:grid-cols-[1fr_1.5fr_auto] md:items-end">
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
          disabled={!name.trim() || createMutation.isPending}
          className="inline-flex items-center justify-center gap-2 rounded-md bg-accent px-4 py-2 text-sm font-medium text-white hover:bg-accent-hover disabled:opacity-60"
        >
          <Plus className="h-4 w-4" aria-hidden="true" />
          Create Set
        </button>
      </form>

      {(createMutation.error || addMutation.error || removeMutation.error) && (
        <ErrorState
          title="Research set action failed"
          message={((createMutation.error || addMutation.error || removeMutation.error) as Error).message}
        />
      )}

      {knowledgeBases.length === 0 ? (
        <EmptyState title="No research sets" description="Create a set to group papers for focused retrieval." />
      ) : (
        <section className="grid gap-4">
          {knowledgeBases.map((kb) => {
            const memberPapers = getMemberPapers(papers, kb);
            const availablePapers = getAvailablePapers(papers, kb);
            const selectedForSet = selectedPaperIds[kb.id] ?? [];
            const paperCount = kb.paper_count ?? kb.paper_ids.length;
            const indexedCount = kb.indexed_count ?? 0;
            const notedCount = kb.noted_count ?? 0;
            const indexedPercent = percent(indexedCount, paperCount);

            return (
              <article key={kb.id} className="rounded-md border border-line bg-panel p-5 shadow-panel">
                <div className="flex items-start justify-between gap-4">
                  <div className="min-w-0">
                    <h2 className="truncate text-base font-semibold text-ink">{kb.name}</h2>
                    <p className="mt-1 text-xs text-muted">{kb.id}</p>
                    {kb.description && <p className="mt-2 text-sm text-muted">{kb.description}</p>}
                  </div>
                  <span className="rounded-full border border-emerald-200 bg-emerald-50 px-2 py-1 text-xs font-medium text-emerald-700">
                    {paperCount} papers
                  </span>
                </div>

                <dl className="mt-4 grid gap-3 sm:grid-cols-3">
                  <div className="rounded-md border border-line bg-surface p-3">
                    <dt className="text-xs uppercase text-muted">Indexed</dt>
                    <dd className="mt-1 text-lg font-semibold text-ink">{indexedCount}/{paperCount}</dd>
                  </div>
                  <div className="rounded-md border border-line bg-surface p-3">
                    <dt className="text-xs uppercase text-muted">Notes</dt>
                    <dd className="mt-1 text-lg font-semibold text-ink">{notedCount}/{paperCount}</dd>
                  </div>
                  <div className="rounded-md border border-line bg-surface p-3">
                    <dt className="text-xs uppercase text-muted">Updated</dt>
                    <dd className="mt-1 truncate text-sm font-medium text-ink">{formatUpdatedAt(kb.updated_at ?? kb.created_at)}</dd>
                  </div>
                </dl>

                <div className="mt-4">
                  <div className="flex items-center justify-between text-xs text-muted">
                    <span>Index coverage</span>
                    <span>{indexedPercent}%</span>
                  </div>
                  <div className="mt-2 h-2 overflow-hidden rounded-full bg-surface">
                    <div className="h-full bg-emerald-50" style={{ width: `${indexedPercent}%` }} />
                  </div>
                </div>

                <div className="mt-5 rounded-md border border-line bg-surface p-3">
                  <div className="mb-3 flex flex-wrap items-center justify-between gap-3">
                    <div>
                      <h3 className="text-sm font-semibold text-ink">Add papers</h3>
                      <p className="text-xs text-muted">{availablePapers.length} available, {selectedForSet.length} selected</p>
                    </div>
                    <button
                      type="button"
                      disabled={selectedForSet.length === 0 || addMutation.isPending}
                      onClick={() => addMutation.mutate({ targetKbId: kb.id, paperIds: selectedForSet })}
                      className="rounded-md border border-line bg-white px-3 py-2 text-sm font-medium text-muted hover:bg-panel disabled:opacity-60"
                    >
                      {selectedForSet.length > 0 ? `Add ${selectedForSet.length} paper${selectedForSet.length > 1 ? "s" : ""}` : "Add selected"}
                    </button>
                  </div>
                  <ResearchSetPaperPicker
                    papers={availablePapers}
                    selectedPaperIds={selectedForSet}
                    onToggle={(paperId) => toggleSelectedPaper(kb.id, paperId)}
                  />
                </div>

                <div className="mt-4 flex flex-wrap gap-2">
                  <a className="inline-flex items-center gap-2 rounded-md border border-line px-3 py-2 text-sm font-medium text-muted hover:bg-surface" href={`/qa?scope=kb&kb_id=${encodeURIComponent(kb.id)}`}>
                    <MessageSquare className="h-4 w-4" aria-hidden="true" />
                    Ask
                  </a>
                  <a className="inline-flex items-center gap-2 rounded-md border border-line px-3 py-2 text-sm font-medium text-muted hover:bg-surface" href={`/compare?kb_id=${encodeURIComponent(kb.id)}`}>
                    <GitCompare className="h-4 w-4" aria-hidden="true" />
                    Compare
                  </a>
                  <a className="inline-flex items-center gap-2 rounded-md border border-line px-3 py-2 text-sm font-medium text-muted hover:bg-surface" href={`/workflow/new?kb_id=${encodeURIComponent(kb.id)}`}>
                    <Workflow className="h-4 w-4" aria-hidden="true" />
                    Workflow
                  </a>
                </div>

                <div className="mt-4 space-y-2">
                  {memberPapers.length === 0 ? (
                    <p className="text-sm text-muted">No papers assigned.</p>
                  ) : (
                    memberPapers.map((paper) => (
                      <div key={paper.paper_id} className="flex items-center justify-between gap-3 rounded-md border border-line bg-surface px-3 py-2">
                        <span className="min-w-0">
                          <span className="block truncate text-sm font-medium text-ink">{paper.title || paper.paper_id}</span>
                          <span className="block truncate text-xs text-muted">{paper.paper_id}</span>
                        </span>
                        <button
                          type="button"
                          onClick={() => removeMutation.mutate({ targetKbId: kb.id, paperId: paper.paper_id })}
                          className="inline-flex h-7 w-7 shrink-0 items-center justify-center rounded border border-line text-muted hover:border-red-200 hover:bg-red-50 hover:text-red-600"
                          aria-label={`Remove ${paper.paper_id} from ${kb.id}`}
                        >
                          <X className="h-4 w-4" aria-hidden="true" />
                        </button>
                      </div>
                    ))
                  )}
                </div>
              </article>
            );
          })}
        </section>
      )}
    </div>
  );
}
