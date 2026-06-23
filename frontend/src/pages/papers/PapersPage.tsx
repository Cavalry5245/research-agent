import { useEffect, useMemo, useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { FileUp, Library, RefreshCw, Search, Trash2 } from "lucide-react";
import { Link } from "react-router-dom";
import {
  deletePaper,
  getLibraryIndexStatus,
  getPapers,
  importPapersFromZotero,
  indexPaper,
  listPaperZoteroCollectionItems,
  listPaperZoteroCollections,
  parsePaper,
  uploadPaper
} from "../../api/papers";
import type { PaperListItem, TaskStatus } from "../../api/types";
import { getTasks } from "../../api/tasks";
import { EmptyState } from "../../components/empty-state/EmptyState";
import { ErrorState } from "../../components/error-state/ErrorState";
import { StatusBadge } from "../../components/status/StatusBadge";

function isTerminalTask(status: TaskStatus["status"]) {
  return status === "completed" || status === "failed" || status === "cancelled";
}

function getIndexButtonLabel(task: TaskStatus | null) {
  if (!task) {
    return "Index";
  }

  if (task.status === "queued") {
    return "Queued";
  }

  if (task.status === "running") {
    return `Indexing ${Math.round((task.progress ?? 0) * 100)}%`;
  }

  if (task.status === "failed") {
    return "Retry index";
  }

  return "Index";
}

type IndexFilter = "all" | "indexed" | "not_indexed";
type SourceFilter = "all" | "upload" | "zotero";
type SortOption =
  | "newest"
  | "oldest"
  | "title_asc"
  | "title_desc"
  | "indexed_first"
  | "not_indexed_first";

interface PaperRow extends PaperListItem {
  indexed: boolean;
}

function getPaperTimestamp(paper: PaperListItem) {
  if (!paper.created_at) {
    return 0;
  }
  const timestamp = Date.parse(paper.created_at);
  return Number.isNaN(timestamp) ? 0 : timestamp;
}

function formatPaperDate(value?: string | null) {
  if (!value) {
    return null;
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return null;
  }
  return date.toLocaleDateString();
}

export function PapersPage() {
  const queryClient = useQueryClient();
  const [search, setSearch] = useState("");
  const [indexFilter, setIndexFilter] = useState<IndexFilter>("all");
  const [sourceFilter, setSourceFilter] = useState<SourceFilter>("all");
  const [sortOption, setSortOption] = useState<SortOption>("newest");
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [confirmingPaperId, setConfirmingPaperId] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [indexTasksByPaperId, setIndexTasksByPaperId] = useState<Record<string, TaskStatus>>({});
  const [showZoteroImport, setShowZoteroImport] = useState(false);
  const [selectedCollectionKey, setSelectedCollectionKey] = useState("");
  const [selectedZoteroItemKeys, setSelectedZoteroItemKeys] = useState<string[]>([]);
  const [zoteroResultSummary, setZoteroResultSummary] = useState<string | null>(null);
  const settledIndexJobIdsRef = useRef<Set<string>>(new Set());

  const papersQuery = useQuery({
    queryKey: ["papers"],
    queryFn: getPapers
  });

  const libraryIndexQuery = useQuery({
    queryKey: ["library-index-status"],
    queryFn: getLibraryIndexStatus
  });

  const activeIndexTaskCount = Object.values(indexTasksByPaperId).filter(
    (task) => !isTerminalTask(task.status)
  ).length;

  const tasksQuery = useQuery({
    queryKey: ["tasks", "paper-index"],
    queryFn: getTasks,
    enabled: activeIndexTaskCount > 0,
    refetchInterval: activeIndexTaskCount > 0 ? 1500 : false
  });

  const zoteroCollectionsQuery = useQuery({
    queryKey: ["paper-zotero-collections"],
    queryFn: listPaperZoteroCollections,
    enabled: showZoteroImport
  });

  const zoteroItemsQuery = useQuery({
    queryKey: ["paper-zotero-items", selectedCollectionKey],
    queryFn: () => listPaperZoteroCollectionItems(selectedCollectionKey),
    enabled: showZoteroImport && !!selectedCollectionKey
  });

  useEffect(() => {
    if (!tasksQuery.data?.jobs.length) {
      return;
    }

    setIndexTasksByPaperId((current) => {
      const next = { ...current };
      for (const task of tasksQuery.data.jobs) {
        if (task.job_type !== "paper_index" || !task.paper_id) {
          continue;
        }
        if (!next[task.paper_id] || next[task.paper_id].job_id === task.job_id) {
          next[task.paper_id] = task;
        }
      }
      return next;
    });
  }, [tasksQuery.data]);

  useEffect(() => {
    if (!tasksQuery.data?.jobs.length) {
      return;
    }

    let shouldRefresh = false;

    for (const task of tasksQuery.data.jobs) {
      if (task.job_type !== "paper_index" || !task.paper_id || !isTerminalTask(task.status)) {
        continue;
      }

      if (settledIndexJobIdsRef.current.has(task.job_id)) {
        continue;
      }

      settledIndexJobIdsRef.current.add(task.job_id);
      shouldRefresh = true;
    }

    if (shouldRefresh) {
      refreshPaperData();
    }
  }, [tasksQuery.data, queryClient]);

  const refreshPaperData = () => {
    void queryClient.invalidateQueries({ queryKey: ["papers"] });
    void queryClient.invalidateQueries({ queryKey: ["library-index-status"] });
    void queryClient.invalidateQueries({ queryKey: ["tasks", "paper-index"] });
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

  const zoteroImportMutation = useMutation({
    mutationFn: () => importPapersFromZotero(selectedCollectionKey, selectedZoteroItemKeys),
    onSuccess: (result) => {
      setActionError(null);
      setSelectedZoteroItemKeys([]);
      setZoteroResultSummary(
        `Imported ${result.imported.length}, skipped ${result.skipped.length}, failed ${result.failed.length}`
      );
      refreshPaperData();
      void queryClient.invalidateQueries({ queryKey: ["paper-zotero-items", selectedCollectionKey] });
    },
    onError: (error) =>
      setActionError(error instanceof Error ? error.message : "Zotero import failed")
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
      setActionError(null);
      if (task.paper_id) {
        setIndexTasksByPaperId((current) => ({
          ...current,
          [task.paper_id as string]: task
        }));
      }
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
  const paperRows = useMemo<PaperRow[]>(() => {
    return papers.map((paper) => ({
      ...paper,
      indexed: indexedPaperIds.has(paper.paper_id)
    }));
  }, [papers, libraryIndexQuery.data?.papers]);

  const filteredPapers = useMemo(() => {
    const query = search.trim().toLowerCase();
    const matches = paperRows.filter((paper) => {
      const matchesSearch =
        !query ||
        paper.paper_id.toLowerCase().includes(query) ||
        paper.title.toLowerCase().includes(query) ||
        paper.abstract.toLowerCase().includes(query);
      const matchesIndex =
        indexFilter === "all" ||
        (indexFilter === "indexed" && paper.indexed) ||
        (indexFilter === "not_indexed" && !paper.indexed);
      const matchesSource = sourceFilter === "all" || (paper.source ?? "upload") === sourceFilter;
      return matchesSearch && matchesIndex && matchesSource;
    });

    return [...matches].sort((left, right) => {
      if (sortOption === "oldest") {
        return getPaperTimestamp(left) - getPaperTimestamp(right);
      }
      if (sortOption === "title_asc") {
        return left.title.localeCompare(right.title);
      }
      if (sortOption === "title_desc") {
        return right.title.localeCompare(left.title);
      }
      if (sortOption === "indexed_first") {
        return Number(right.indexed) - Number(left.indexed);
      }
      if (sortOption === "not_indexed_first") {
        return Number(left.indexed) - Number(right.indexed);
      }
      return getPaperTimestamp(right) - getPaperTimestamp(left);
    });
  }, [indexFilter, paperRows, search, sortOption, sourceFilter]);

  const toggleZoteroItem = (itemKey: string) => {
    setSelectedZoteroItemKeys((current) =>
      current.includes(itemKey) ? current.filter((key) => key !== itemKey) : [...current, itemKey]
    );
  };

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
            Upload PDFs, auto-parse them on ingest, then index each paper for search and QA.
          </p>
        </div>
        <div className="flex flex-col gap-2">
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
          <button
            type="button"
            onClick={() => {
              setShowZoteroImport((current) => !current);
              setActionError(null);
            }}
            className="inline-flex items-center justify-center gap-2 rounded-md border border-line bg-panel px-3 py-2 text-sm font-medium text-muted hover:bg-surface hover:text-ink"
          >
            <Library className="h-4 w-4" aria-hidden="true" />
            {showZoteroImport ? "Hide Zotero import" : "Import from Zotero"}
          </button>
        </div>
      </section>

      {actionError && <ErrorState title="Paper action failed" message={actionError} />}

      {showZoteroImport && (
        <section className="rounded-md border border-line bg-panel p-4 shadow-panel">
          <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
            <div>
              <h2 className="text-base font-semibold text-ink">Import from Zotero</h2>
              <p className="mt-1 text-sm text-muted">
                Select a Zotero collection, then import PDF attachments into the local paper library.
              </p>
            </div>
            {zoteroResultSummary && (
              <p className="rounded-full border border-emerald-200 bg-emerald-50 px-3 py-1 text-xs font-medium text-emerald-700">
                {zoteroResultSummary}
              </p>
            )}
          </div>

          <div className="mt-4 grid gap-4 lg:grid-cols-[minmax(240px,320px),1fr]">
            <label className="block">
              <span className="text-xs font-medium uppercase text-muted">Collection</span>
              <select
                value={selectedCollectionKey}
                onChange={(event) => {
                  setSelectedCollectionKey(event.target.value);
                  setSelectedZoteroItemKeys([]);
                  setZoteroResultSummary(null);
                }}
                disabled={zoteroCollectionsQuery.isLoading}
                className="mt-1 w-full rounded-md border border-line bg-panel px-3 py-2 text-sm text-ink disabled:opacity-60"
              >
                <option value="">
                  {zoteroCollectionsQuery.isLoading ? "Loading collections..." : "Choose a collection"}
                </option>
                {(zoteroCollectionsQuery.data?.collections ?? []).map((collection) => (
                  <option key={collection.key} value={collection.key}>
                    {collection.name} ({collection.num_items ?? 0})
                  </option>
                ))}
              </select>
              {zoteroCollectionsQuery.error && (
                <span className="mt-2 block text-xs text-red-600">
                  {(zoteroCollectionsQuery.error as Error).message}
                </span>
              )}
            </label>

            <div className="rounded-md border border-line">
              <div className="flex items-center justify-between border-b border-line px-3 py-2">
                <p className="text-xs font-medium uppercase text-muted">Collection PDFs</p>
                <button
                  type="button"
                  disabled={!selectedZoteroItemKeys.length || zoteroImportMutation.isPending}
                  onClick={() => zoteroImportMutation.mutate()}
                  className="rounded-md bg-accent px-3 py-1.5 text-xs font-medium text-white hover:bg-accent-hover disabled:cursor-not-allowed disabled:opacity-60"
                >
                  {zoteroImportMutation.isPending
                    ? "Importing"
                    : `Import selected (${selectedZoteroItemKeys.length})`}
                </button>
              </div>
              {!selectedCollectionKey ? (
                <p className="px-3 py-4 text-sm text-muted">Choose a collection to see Zotero items.</p>
              ) : zoteroItemsQuery.isLoading ? (
                <p className="px-3 py-4 text-sm text-muted">Loading Zotero items...</p>
              ) : zoteroItemsQuery.error ? (
                <p className="px-3 py-4 text-sm text-red-600">{(zoteroItemsQuery.error as Error).message}</p>
              ) : (zoteroItemsQuery.data?.items ?? []).length === 0 ? (
                <p className="px-3 py-4 text-sm text-muted">No importable Zotero items found.</p>
              ) : (
                <div className="max-h-80 overflow-auto divide-y divide-line">
                  {(zoteroItemsQuery.data?.items ?? []).map((item) => {
                    const disabled = !item.has_pdf || item.already_imported;
                    return (
                      <label
                        key={item.key}
                        className={`flex items-start gap-3 px-3 py-3 hover:bg-surface ${
                          disabled ? "cursor-not-allowed opacity-60" : "cursor-pointer"
                        }`}
                      >
                        <input
                          type="checkbox"
                          checked={selectedZoteroItemKeys.includes(item.key)}
                          disabled={disabled}
                          onChange={() => toggleZoteroItem(item.key)}
                          className="mt-1 h-4 w-4 rounded border-line"
                        />
                        <span className="min-w-0 flex-1">
                          <span className="block truncate text-sm font-medium text-ink">
                            {item.title || "Untitled Zotero item"}
                          </span>
                          <span className="mt-1 block text-xs text-muted">
                            {[item.creators.join(", "), item.year].filter(Boolean).join(" · ") || item.key}
                          </span>
                        </span>
                        <span className="rounded-full border border-line px-2 py-0.5 text-xs text-muted">
                          {item.already_imported ? "imported" : item.has_pdf ? "PDF" : "no PDF"}
                        </span>
                      </label>
                    );
                  })}
                </div>
              )}
            </div>
          </div>
        </section>
      )}

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
          <div className="flex w-full flex-col gap-2 xl:flex-row xl:items-center">
            <label className="relative block w-full xl:max-w-md">
              <Search className="pointer-events-none absolute left-3 top-2.5 h-4 w-4 text-muted" aria-hidden="true" />
              <input
                value={search}
                onChange={(event) => setSearch(event.target.value)}
                placeholder="Search title, abstract, or ID"
                className="w-full rounded-md border border-line bg-panel py-2 pl-9 pr-3 text-sm text-ink"
              />
            </label>
            <select
              value={sortOption}
              onChange={(event) => setSortOption(event.target.value as SortOption)}
              className="rounded-md border border-line bg-panel px-3 py-2 text-sm text-muted"
              aria-label="Sort papers"
            >
              <option value="newest">Newest first</option>
              <option value="oldest">Oldest first</option>
              <option value="title_asc">Title A-Z</option>
              <option value="title_desc">Title Z-A</option>
              <option value="indexed_first">Indexed first</option>
              <option value="not_indexed_first">Not indexed first</option>
            </select>
            <select
              value={indexFilter}
              onChange={(event) => setIndexFilter(event.target.value as IndexFilter)}
              className="rounded-md border border-line bg-panel px-3 py-2 text-sm text-muted"
              aria-label="Filter by index status"
            >
              <option value="all">All index states</option>
              <option value="indexed">Indexed only</option>
              <option value="not_indexed">Not indexed only</option>
            </select>
            <select
              value={sourceFilter}
              onChange={(event) => setSourceFilter(event.target.value as SourceFilter)}
              className="rounded-md border border-line bg-panel px-3 py-2 text-sm text-muted"
              aria-label="Filter by source"
            >
              <option value="all">All sources</option>
              <option value="upload">Uploaded</option>
              <option value="zotero">Zotero</option>
            </select>
          </div>
          <div className="flex items-center gap-2">
            <span className="whitespace-nowrap text-xs text-muted">
              Showing {filteredPapers.length} / {papers.length}
            </span>
            <button
              type="button"
              onClick={refreshPaperData}
              className="inline-flex items-center gap-2 rounded-md border border-line px-3 py-2 text-sm text-muted hover:bg-surface hover:text-ink"
            >
              <RefreshCw className="h-4 w-4" aria-hidden="true" />
              Refresh
            </button>
          </div>
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
                    (parseMutation.isPending && parseMutation.variables === paper.paper_id) ||
                    (indexMutation.isPending && indexMutation.variables === paper.paper_id) ||
                    (deleteMutation.isPending && deleteMutation.variables === paper.paper_id);
                  const indexTask = indexTasksByPaperId[paper.paper_id] ?? null;
                  const showIndexProgress =
                    indexTask && !isTerminalTask(indexTask.status) && !paper.indexed;
                  const progressPercent = Math.max(
                    6,
                    Math.round((indexTask?.progress ?? 0) * 100)
                  );
                  const createdDate = formatPaperDate(paper.created_at);
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
                        <div className="mt-2 flex flex-wrap items-center gap-2 text-xs text-muted">
                          <span className="rounded-full border border-line px-2 py-0.5">
                            {(paper.source ?? "upload") === "zotero" ? "Zotero" : "Upload"}
                          </span>
                          {createdDate && <span>Imported {createdDate}</span>}
                        </div>
                      </td>
                      <td className="px-4 py-3">
                        <StatusBadge status={paper.indexed ? "completed" : "queued"} label={paper.indexed ? "indexed" : "not indexed"} />
                      </td>
                      <td className="px-4 py-3">
                        <div className="flex flex-wrap justify-end gap-2">
                          <button
                            type="button"
                            onClick={() => parseMutation.mutate(paper.paper_id)}
                            disabled={busy}
                            className="rounded border border-line px-2 py-1 text-xs font-medium text-muted hover:bg-surface disabled:opacity-60"
                          >
                            Re-parse
                          </button>
                          <button
                            type="button"
                            onClick={() => indexMutation.mutate(paper.paper_id)}
                            disabled={busy || showIndexProgress}
                            className="relative overflow-hidden rounded border border-line px-2 py-1 text-xs font-medium text-muted hover:bg-surface disabled:opacity-60"
                          >
                            {showIndexProgress && (
                              <span
                                aria-hidden="true"
                                className="absolute inset-y-0 left-0 bg-emerald-50"
                                style={{ width: `${progressPercent}%` }}
                              />
                            )}
                            <span className="relative z-10">{getIndexButtonLabel(indexTask)}</span>
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
