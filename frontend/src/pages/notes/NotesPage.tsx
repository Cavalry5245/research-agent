import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Download, Eye, RefreshCw, Search } from "lucide-react";
import { getNoteStatuses, getPaperNote, generatePaperNote, downloadPaperNote } from "../../api/notes";
import { getPapers } from "../../api/papers";
import type { NoteStatusItem, PaperListItem } from "../../api/types";
import { EmptyState } from "../../components/empty-state/EmptyState";
import { ErrorState } from "../../components/error-state/ErrorState";
import { StatusBadge } from "../../components/status/StatusBadge";
import { MarkdownContent } from "../../components/common/MarkdownContent";

type NoteFilter = "all" | "generated" | "missing";
type NoteSort = "paper_newest" | "title_asc" | "generated_newest" | "missing_first";

interface NoteRow extends PaperListItem {
  note: NoteStatusItem | null;
}

function getTimestamp(value?: string | null) {
  if (!value) {
    return 0;
  }
  const timestamp = Date.parse(value);
  return Number.isNaN(timestamp) ? 0 : timestamp;
}

function formatDate(value?: string | null) {
  if (!value) {
    return null;
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return null;
  }
  return date.toLocaleString();
}

export function NotesPage() {
  const queryClient = useQueryClient();
  const [selectedPaperId, setSelectedPaperId] = useState("");
  const [search, setSearch] = useState("");
  const [filter, setFilter] = useState<NoteFilter>("all");
  const [sort, setSort] = useState<NoteSort>("missing_first");
  const [confirmingRegeneratePaperId, setConfirmingRegeneratePaperId] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);

  const papersQuery = useQuery({
    queryKey: ["papers"],
    queryFn: getPapers
  });

  const noteStatusesQuery = useQuery({
    queryKey: ["notes-status"],
    queryFn: getNoteStatuses,
    enabled: papersQuery.isSuccess
  });

  const noteQuery = useQuery({
    queryKey: ["paper-note", selectedPaperId],
    queryFn: () => getPaperNote(selectedPaperId),
    enabled: !!selectedPaperId,
    retry: false
  });

  const refreshNotes = () => {
    void queryClient.invalidateQueries({ queryKey: ["notes-status"] });
    if (selectedPaperId) {
      void queryClient.invalidateQueries({ queryKey: ["paper-note", selectedPaperId] });
    }
  };

  const generateMutation = useMutation({
    mutationFn: generatePaperNote,
    onSuccess: (_, paperId) => {
      setSelectedPaperId(paperId);
      setConfirmingRegeneratePaperId(null);
      setActionError(null);
      void queryClient.invalidateQueries({ queryKey: ["notes-status"] });
      void queryClient.invalidateQueries({ queryKey: ["paper-note", paperId] });
    },
    onError: (error) => setActionError(error instanceof Error ? error.message : "Note generation failed")
  });

  const downloadMutation = useMutation({
    mutationFn: downloadPaperNote,
    onSuccess: () => setActionError(null),
    onError: (error) => setActionError(error instanceof Error ? error.message : "Note download failed")
  });

  const papers = papersQuery.data?.papers ?? [];
  const noteStatuses = noteStatusesQuery.data?.notes ?? [];
  const noteStatusByPaperId = new Map(noteStatuses.map((note) => [note.paper_id, note]));
  const rows = useMemo<NoteRow[]>(() => {
    const query = search.trim().toLowerCase();
    const mergedRows = papers.map((paper) => ({
      ...paper,
      note: noteStatusByPaperId.get(paper.paper_id) ?? null
    }));

    const filteredRows = mergedRows.filter((paper) => {
      const hasNote = paper.note?.exists ?? false;
      const matchesFilter =
        filter === "all" ||
        (filter === "generated" && hasNote) ||
        (filter === "missing" && !hasNote);
      const matchesSearch =
        !query ||
        paper.paper_id.toLowerCase().includes(query) ||
        paper.title.toLowerCase().includes(query) ||
        paper.abstract.toLowerCase().includes(query);
      return matchesFilter && matchesSearch;
    });

    return [...filteredRows].sort((left, right) => {
      if (sort === "title_asc") {
        return left.title.localeCompare(right.title);
      }
      if (sort === "generated_newest") {
        return getTimestamp(right.note?.generated_at) - getTimestamp(left.note?.generated_at);
      }
      if (sort === "paper_newest") {
        return getTimestamp(right.created_at) - getTimestamp(left.created_at);
      }
      return Number(left.note?.exists ?? false) - Number(right.note?.exists ?? false);
    });
  }, [filter, noteStatuses, papers, search, sort]);

  const generatedCount = papers.filter((paper) => noteStatusByPaperId.get(paper.paper_id)?.exists).length;
  const selectedPaper = papers.find((paper) => paper.paper_id === selectedPaperId);
  const selectedStatus = selectedPaperId ? noteStatusByPaperId.get(selectedPaperId) : null;
  const selectedGeneratedAt = formatDate(selectedStatus?.generated_at);

  if (papersQuery.isLoading) {
    return <p className="text-sm text-muted">Loading papers...</p>;
  }

  if (papersQuery.error) {
    return <ErrorState title="Unable to load papers" message={(papersQuery.error as Error).message} />;
  }

  return (
    <div className="space-y-6">
      <section className="flex flex-col gap-4 xl:flex-row xl:items-end xl:justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-ink">Notes</h1>
          <p className="mt-2 max-w-3xl text-sm leading-6 text-muted">
            Manage Markdown notes across papers: find missing notes, preview existing ones, and regenerate when needed.
          </p>
        </div>
        <button
          type="button"
          onClick={refreshNotes}
          className="inline-flex items-center justify-center gap-2 rounded-md border border-line bg-panel px-3 py-2 text-sm font-medium text-muted hover:bg-surface hover:text-ink"
        >
          <RefreshCw className="h-4 w-4" aria-hidden="true" />
          Refresh notes
        </button>
      </section>

      {papers.length === 0 && <EmptyState title="No papers available" description="Upload papers before generating notes." />}
      {actionError && <ErrorState title="Note action failed" message={actionError} />}
      {noteStatusesQuery.error && (
        <ErrorState
          title="Unable to load note status"
          message={(noteStatusesQuery.error as Error).message}
        />
      )}

      <section className="grid gap-4 md:grid-cols-3">
        <div className="rounded-md border border-line bg-panel p-4 shadow-panel">
          <p className="text-xs font-medium uppercase text-muted">Papers</p>
          <p className="mt-2 text-2xl font-semibold text-ink">{papers.length}</p>
        </div>
        <div className="rounded-md border border-line bg-panel p-4 shadow-panel">
          <p className="text-xs font-medium uppercase text-muted">Notes generated</p>
          <p className="mt-2 text-2xl font-semibold text-ink">{generatedCount}</p>
        </div>
        <div className="rounded-md border border-line bg-panel p-4 shadow-panel">
          <p className="text-xs font-medium uppercase text-muted">Missing notes</p>
          <p className="mt-2 text-2xl font-semibold text-ink">{Math.max(papers.length - generatedCount, 0)}</p>
        </div>
      </section>

      {papers.length > 0 && (
        <section className="grid gap-6 min-[1800px]:grid-cols-[minmax(0,1.2fr),minmax(420px,0.8fr)]">
          <div className="rounded-md border border-line bg-panel shadow-panel">
            <div className="flex flex-col gap-3 border-b border-line p-4">
              <div className="flex flex-col gap-2 lg:flex-row lg:items-center">
                <label className="relative block w-full">
                  <Search className="pointer-events-none absolute left-3 top-2.5 h-4 w-4 text-muted" aria-hidden="true" />
                  <input
                    value={search}
                    onChange={(event) => setSearch(event.target.value)}
                    placeholder="Search title, abstract, or ID"
                    className="w-full rounded-md border border-line bg-panel py-2 pl-9 pr-3 text-sm text-ink"
                  />
                </label>
                <select
                  value={filter}
                  onChange={(event) => setFilter(event.target.value as NoteFilter)}
                  className="rounded-md border border-line bg-panel px-3 py-2 text-sm text-muted"
                  aria-label="Filter notes"
                >
                  <option value="all">All notes</option>
                  <option value="generated">Generated only</option>
                  <option value="missing">Missing only</option>
                </select>
                <select
                  value={sort}
                  onChange={(event) => setSort(event.target.value as NoteSort)}
                  className="rounded-md border border-line bg-panel px-3 py-2 text-sm text-muted"
                  aria-label="Sort notes"
                >
                  <option value="missing_first">Missing first</option>
                  <option value="generated_newest">Recently generated</option>
                  <option value="paper_newest">Newest paper</option>
                  <option value="title_asc">Title A-Z</option>
                </select>
              </div>
              <p className="text-xs text-muted">
                Showing {rows.length} / {papers.length}
              </p>
            </div>

            {noteStatusesQuery.isLoading ? (
              <p className="p-4 text-sm text-muted">Loading note status...</p>
            ) : rows.length === 0 ? (
              <div className="p-4">
                <EmptyState title="No matching papers" description="Try a different search or note filter." />
              </div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full min-w-[720px] table-fixed divide-y divide-line">
                  <thead className="bg-surface">
                    <tr>
                      <th className="w-44 px-4 py-3 text-left text-xs font-medium uppercase text-muted">Paper ID</th>
                      <th className="px-4 py-3 text-left text-xs font-medium uppercase text-muted">Title</th>
                      <th className="w-24 px-3 py-3 text-left text-xs font-medium uppercase text-muted">Note</th>
                      <th className="sticky right-0 w-40 bg-surface px-3 py-3 text-right text-xs font-medium uppercase text-muted shadow-[-8px_0_12px_-12px_rgba(15,23,42,0.35)]">Actions</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-line">
                    {rows.map((paper) => {
                      const hasNote = paper.note?.exists ?? false;
                      const generatedAt = formatDate(paper.note?.generated_at);
                      const generating =
                        generateMutation.isPending && generateMutation.variables === paper.paper_id;
                      const downloading =
                        downloadMutation.isPending && downloadMutation.variables === paper.paper_id;
                      const confirming = confirmingRegeneratePaperId === paper.paper_id;
                      return (
                        <tr
                          key={paper.paper_id}
                          className={`group align-top hover:bg-surface ${selectedPaperId === paper.paper_id ? "bg-surface" : ""}`}
                        >
                          <td className="px-4 py-3 text-sm font-medium text-accent">
                            <span className="block truncate" title={paper.paper_id}>
                              {paper.paper_id}
                            </span>
                          </td>
                          <td className="px-4 py-3">
                            <p className="line-clamp-2 text-sm font-medium text-ink">{paper.title || "Untitled paper"}</p>
                            {generatedAt && <p className="mt-2 text-xs text-muted">Generated {generatedAt}</p>}
                          </td>
                          <td className="px-3 py-3">
                            <StatusBadge
                              status={hasNote ? "completed" : "queued"}
                              label={hasNote ? "generated" : "missing"}
                            />
                          </td>
                          <td
                            className={`sticky right-0 px-3 py-3 shadow-[-8px_0_12px_-12px_rgba(15,23,42,0.35)] ${
                              selectedPaperId === paper.paper_id ? "bg-surface" : "bg-panel group-hover:bg-surface"
                            }`}
                          >
                            <div className="flex flex-wrap justify-end gap-1.5">
                              {hasNote && (
                                <>
                                  <button
                                    type="button"
                                    onClick={() => setSelectedPaperId(paper.paper_id)}
                                    className="inline-flex items-center gap-1 rounded border border-line px-2 py-1 text-xs font-medium text-muted hover:bg-surface"
                                  >
                                    <Eye className="h-3.5 w-3.5" aria-hidden="true" />
                                    View
                                  </button>
                                  <button
                                    type="button"
                                    onClick={() => downloadMutation.mutate(paper.paper_id)}
                                    disabled={downloading}
                                    className="inline-flex items-center gap-1 rounded border border-line px-2 py-1 text-xs font-medium text-muted hover:bg-surface disabled:opacity-60"
                                  >
                                    <Download className="h-3.5 w-3.5" aria-hidden="true" />
                                    {downloading ? "Downloading" : "Download"}
                                  </button>
                                </>
                              )}
                              {hasNote && confirming ? (
                                <>
                                  <button
                                    type="button"
                                    onClick={() => generateMutation.mutate(paper.paper_id)}
                                    disabled={generating}
                                    className="rounded border border-amber-200 px-2 py-1 text-xs font-medium text-amber-700 hover:bg-amber-50 disabled:opacity-60"
                                  >
                                    {generating ? "Regenerating" : "Confirm"}
                                  </button>
                                  <button
                                    type="button"
                                    onClick={() => setConfirmingRegeneratePaperId(null)}
                                    className="rounded border border-line px-2 py-1 text-xs font-medium text-muted hover:bg-surface"
                                  >
                                    Cancel
                                  </button>
                                </>
                              ) : (
                                <button
                                  type="button"
                                  onClick={() =>
                                    hasNote
                                      ? setConfirmingRegeneratePaperId(paper.paper_id)
                                      : generateMutation.mutate(paper.paper_id)
                                  }
                                  disabled={generating}
                                  className="rounded bg-accent px-2 py-1 text-xs font-medium text-white hover:bg-accent-hover disabled:opacity-60"
                                >
                                  {generating ? "Generating" : hasNote ? "Regenerate" : "Generate"}
                                </button>
                              )}
                            </div>
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            )}
          </div>

          <div className="rounded-md border border-line bg-panel shadow-panel">
            <div className="border-b border-line p-4">
              <h2 className="text-sm font-semibold text-ink">Note preview</h2>
              {selectedPaper ? (
                <div className="mt-1 space-y-1">
                  <p className="line-clamp-1 text-xs text-muted">{selectedPaper.title}</p>
                  {selectedGeneratedAt && <p className="text-xs text-muted">Generated {selectedGeneratedAt}</p>}
                </div>
              ) : (
                <p className="mt-1 text-xs text-muted">Select a generated note to preview it here.</p>
              )}
            </div>
            <div className="p-4">
              {!selectedPaperId ? (
                <EmptyState title="Select a note" description="Use View on a generated note, or generate one from the table." />
              ) : noteQuery.isLoading ? (
                <p className="text-sm text-muted">Loading note...</p>
              ) : noteQuery.isSuccess ? (
                <MarkdownContent
                  content={noteQuery.data.content}
                  className="max-h-[40rem] overflow-auto rounded-md bg-surface p-4"
                />
              ) : (
                <EmptyState title="No note found" description="Generate this paper's note to preview it here." />
              )}
            </div>
          </div>
        </section>
      )}
    </div>
  );
}
