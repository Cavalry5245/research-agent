import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { FileUp, RefreshCw, Search, Trash2 } from "lucide-react";
import { Link } from "react-router-dom";
import {
  deletePaper,
  getLibraryIndexStatus,
  getPapers,
  indexPaper,
  parsePaper,
  uploadPaper
} from "../../api/papers";
import type { TaskStatus } from "../../api/types";
import { EmptyState } from "../../components/empty-state/EmptyState";
import { ErrorState } from "../../components/error-state/ErrorState";
import { StatusBadge } from "../../components/status/StatusBadge";
import { TaskStatusPanel } from "../../components/tasks/TaskStatusPanel";

export function PapersPage() {
  const queryClient = useQueryClient();
  const [search, setSearch] = useState("");
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [confirmingPaperId, setConfirmingPaperId] = useState<string | null>(null);
  const [latestTask, setLatestTask] = useState<TaskStatus | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);

  const papersQuery = useQuery({
    queryKey: ["papers"],
    queryFn: getPapers
  });

  const libraryIndexQuery = useQuery({
    queryKey: ["library-index-status"],
    queryFn: getLibraryIndexStatus
  });

  const refreshPaperData = () => {
    void queryClient.invalidateQueries({ queryKey: ["papers"] });
    void queryClient.invalidateQueries({ queryKey: ["library-index-status"] });
  };

  const uploadMutation = useMutation({
    mutationFn: uploadPaper,
    onSuccess: () => {
      setSelectedFile(null);
      setActionError(null);
      refreshPaperData();
    },
    onError: (error) => setActionError(error instanceof Error ? error.message : "Upload failed")
  });

  const parseMutation = useMutation({
    mutationFn: parsePaper,
    onSuccess: () => {
      setActionError(null);
      refreshPaperData();
    },
    onError: (error) => setActionError(error instanceof Error ? error.message : "Parse failed")
  });

  const indexMutation = useMutation({
    mutationFn: (paperId: string) => indexPaper(paperId),
    onSuccess: (task) => {
      setLatestTask(task);
      setActionError(null);
      refreshPaperData();
    },
    onError: (error) => setActionError(error instanceof Error ? error.message : "Index failed")
  });

  const deleteMutation = useMutation({
    mutationFn: deletePaper,
    onSuccess: () => {
      setConfirmingPaperId(null);
      setActionError(null);
      refreshPaperData();
    },
    onError: (error) => setActionError(error instanceof Error ? error.message : "Delete failed")
  });

  const papers = papersQuery.data?.papers ?? [];
  const indexedPaperIds = new Set((libraryIndexQuery.data?.papers ?? []).map((paper) => paper.paper_id));
  const filteredPapers = useMemo(() => {
    const query = search.trim().toLowerCase();
    if (!query) return papers;
    return papers.filter((paper) => {
      return (
        paper.paper_id.toLowerCase().includes(query) ||
        paper.title.toLowerCase().includes(query) ||
        paper.abstract.toLowerCase().includes(query)
      );
    });
  }, [papers, search]);

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
          <h1 className="text-2xl font-semibold text-ink">Papers</h1>
          <p className="mt-2 max-w-3xl text-sm leading-6 text-muted">
            Upload, parse, index, search, and inspect the local paper library.
          </p>
        </div>
        <form
          className="flex flex-col gap-2 rounded-md border border-line bg-panel p-3 md:flex-row md:items-center"
          onSubmit={(event) => {
            event.preventDefault();
            if (selectedFile) uploadMutation.mutate(selectedFile);
          }}
        >
          <label className="inline-flex cursor-pointer items-center gap-2 rounded-md border border-line px-3 py-2 text-sm text-muted hover:bg-surface">
            <FileUp className="h-4 w-4" aria-hidden="true" />
            <span>{selectedFile ? selectedFile.name : "Choose PDF"}</span>
            <input
              type="file"
              accept="application/pdf,.pdf"
              className="sr-only"
              onChange={(event) => setSelectedFile(event.target.files?.[0] ?? null)}
            />
          </label>
          <button
            type="submit"
            disabled={!selectedFile || uploadMutation.isPending}
            className="rounded-md bg-accent px-4 py-2 text-sm font-medium text-white hover:bg-accent-hover disabled:cursor-not-allowed disabled:opacity-60"
          >
            {uploadMutation.isPending ? "Uploading" : "Upload"}
          </button>
        </form>
      </section>

      {actionError && <ErrorState title="Paper action failed" message={actionError} />}
      <TaskStatusPanel task={latestTask} title="Latest index task" />

      <section className="grid gap-4 md:grid-cols-3">
        <div className="rounded-md border border-line bg-panel p-4 shadow-panel">
          <p className="text-xs font-medium uppercase text-muted">Papers</p>
          <p className="mt-2 text-2xl font-semibold text-ink">{papers.length}</p>
        </div>
        <div className="rounded-md border border-line bg-panel p-4 shadow-panel">
          <p className="text-xs font-medium uppercase text-muted">Indexed papers</p>
          <p className="mt-2 text-2xl font-semibold text-ink">{libraryIndexQuery.data?.paper_count ?? 0}</p>
        </div>
        <div className="rounded-md border border-line bg-panel p-4 shadow-panel">
          <p className="text-xs font-medium uppercase text-muted">Indexed chunks</p>
          <p className="mt-2 text-2xl font-semibold text-ink">{libraryIndexQuery.data?.total_chunks ?? 0}</p>
        </div>
      </section>

      <section className="rounded-md border border-line bg-panel shadow-panel">
        <div className="flex flex-col gap-3 border-b border-line p-4 md:flex-row md:items-center md:justify-between">
          <label className="relative block w-full md:max-w-md">
            <Search className="pointer-events-none absolute left-3 top-2.5 h-4 w-4 text-muted" aria-hidden="true" />
            <input
              value={search}
              onChange={(event) => setSearch(event.target.value)}
              placeholder="Search title, abstract, or ID"
              className="w-full rounded-md border border-line bg-panel py-2 pl-9 pr-3 text-sm text-ink"
            />
          </label>
          <button
            type="button"
            onClick={refreshPaperData}
            className="inline-flex items-center gap-2 rounded-md border border-line px-3 py-2 text-sm text-muted hover:bg-surface hover:text-ink"
          >
            <RefreshCw className="h-4 w-4" aria-hidden="true" />
            Refresh
          </button>
        </div>

        {papers.length === 0 ? (
          <div className="p-4">
            <EmptyState title="No papers yet" description="Upload a PDF to add the first paper to the local library." />
          </div>
        ) : filteredPapers.length === 0 ? (
          <div className="p-4">
            <EmptyState title="No matching papers" description="Try a different search term." />
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[880px] table-fixed divide-y divide-line">
              <thead className="bg-surface">
                <tr>
                  <th className="w-44 px-4 py-3 text-left text-xs font-medium uppercase text-muted">Paper ID</th>
                  <th className="px-4 py-3 text-left text-xs font-medium uppercase text-muted">Title</th>
                  <th className="w-28 px-4 py-3 text-left text-xs font-medium uppercase text-muted">Index</th>
                  <th className="w-72 px-4 py-3 text-right text-xs font-medium uppercase text-muted">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-line">
                {filteredPapers.map((paper) => {
                  const confirming = confirmingPaperId === paper.paper_id;
                  const busy =
                    parseMutation.variables === paper.paper_id ||
                    indexMutation.variables === paper.paper_id ||
                    deleteMutation.variables === paper.paper_id;
                  const indexed = indexedPaperIds.has(paper.paper_id);
                  return (
                    <tr key={paper.paper_id} className="align-top hover:bg-surface">
                      <td className="px-4 py-3">
                        <Link to={`/papers/${paper.paper_id}`} className="text-sm font-medium text-accent hover:underline">
                          {paper.paper_id}
                        </Link>
                      </td>
                      <td className="px-4 py-3">
                        <p className="line-clamp-2 text-sm font-medium text-ink">{paper.title || "Untitled paper"}</p>
                        <p className="mt-1 line-clamp-2 text-xs text-muted">{paper.abstract || "No abstract available."}</p>
                      </td>
                      <td className="px-4 py-3">
                        <StatusBadge status={indexed ? "completed" : "queued"} label={indexed ? "indexed" : "not indexed"} />
                      </td>
                      <td className="px-4 py-3">
                        <div className="flex flex-wrap justify-end gap-2">
                          <button
                            type="button"
                            onClick={() => parseMutation.mutate(paper.paper_id)}
                            disabled={busy}
                            className="rounded border border-line px-2 py-1 text-xs font-medium text-muted hover:bg-surface disabled:opacity-60"
                          >
                            Parse
                          </button>
                          <button
                            type="button"
                            onClick={() => indexMutation.mutate(paper.paper_id)}
                            disabled={busy}
                            className="rounded border border-line px-2 py-1 text-xs font-medium text-muted hover:bg-surface disabled:opacity-60"
                          >
                            Index
                          </button>
                          {confirming ? (
                            <>
                              <button
                                type="button"
                                onClick={() => deleteMutation.mutate(paper.paper_id)}
                                disabled={deleteMutation.isPending}
                                className="rounded border border-red-200 px-2 py-1 text-xs font-medium text-red-600 hover:bg-red-50 disabled:opacity-60"
                              >
                                Confirm
                              </button>
                              <button
                                type="button"
                                onClick={() => setConfirmingPaperId(null)}
                                className="rounded border border-line px-2 py-1 text-xs font-medium text-muted hover:bg-surface"
                              >
                                Cancel
                              </button>
                            </>
                          ) : (
                            <button
                              type="button"
                              onClick={() => setConfirmingPaperId(paper.paper_id)}
                              className="inline-flex h-7 w-7 items-center justify-center rounded border border-line text-muted hover:border-red-200 hover:bg-red-50 hover:text-red-600"
                              aria-label={`Delete ${paper.paper_id}`}
                              title="Delete paper"
                            >
                              <Trash2 className="h-4 w-4" aria-hidden="true" />
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
      </section>
    </div>
  );
}
