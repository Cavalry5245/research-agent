import { useParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, Download, FileText, Pencil, RefreshCw } from "lucide-react";
import { Link } from "react-router-dom";
import { getPaperNote, generatePaperNote, downloadPaperNote } from "../../api/notes";
import { getPaperIndexStatus, getPapers, indexPaper, parsePaper, updatePaperTitle } from "../../api/papers";
import type { TaskStatus } from "../../api/types";
import { EmptyState } from "../../components/empty-state/EmptyState";
import { ErrorState } from "../../components/error-state/ErrorState";
import { StatusBadge } from "../../components/status/StatusBadge";
import { TaskStatusPanel } from "../../components/tasks/TaskStatusPanel";
import { MarkdownContent } from "../../components/common/MarkdownContent";
import { useEffect, useState } from "react";

export function PaperDetailPage() {
  const { paperId } = useParams();
  const queryClient = useQueryClient();
  const [latestTask, setLatestTask] = useState<TaskStatus | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [isEditingTitle, setIsEditingTitle] = useState(false);
  const [draftTitle, setDraftTitle] = useState("");

  const papersQuery = useQuery({
    queryKey: ["papers"],
    queryFn: getPapers
  });

  const indexQuery = useQuery({
    queryKey: ["paper-index-status", paperId],
    queryFn: () => getPaperIndexStatus(paperId!),
    enabled: !!paperId
  });

  const noteQuery = useQuery({
    queryKey: ["paper-note", paperId],
    queryFn: () => getPaperNote(paperId!),
    enabled: !!paperId,
    retry: false
  });

  const refreshDetail = () => {
    void queryClient.invalidateQueries({ queryKey: ["papers"] });
    void queryClient.invalidateQueries({ queryKey: ["paper-index-status", paperId] });
    void queryClient.invalidateQueries({ queryKey: ["paper-note", paperId] });
  };

  const parseMutation = useMutation({
    mutationFn: () => parsePaper(paperId!),
    onSuccess: () => {
      setActionError(null);
      refreshDetail();
    },
    onError: (error) => setActionError(error instanceof Error ? error.message : "Parse failed")
  });

  const indexMutation = useMutation({
    mutationFn: () => indexPaper(paperId!),
    onSuccess: (task) => {
      setLatestTask(task);
      setActionError(null);
      refreshDetail();
    },
    onError: (error) => setActionError(error instanceof Error ? error.message : "Index failed")
  });

  const noteMutation = useMutation({
    mutationFn: () => generatePaperNote(paperId!),
    onSuccess: () => {
      setActionError(null);
      refreshDetail();
    },
    onError: (error) => setActionError(error instanceof Error ? error.message : "Note generation failed")
  });

  const downloadMutation = useMutation({
    mutationFn: () => downloadPaperNote(paperId!),
    onSuccess: () => setActionError(null),
    onError: (error) => setActionError(error instanceof Error ? error.message : "Note download failed")
  });

  const titleMutation = useMutation({
    mutationFn: (title: string) => updatePaperTitle(paperId!, title),
    onSuccess: (result) => {
      setActionError(null);
      setDraftTitle(result.title);
      setIsEditingTitle(false);
      refreshDetail();
    },
    onError: (error) => setActionError(error instanceof Error ? error.message : "Title update failed")
  });

  const paper = papersQuery.data?.papers.find((item) => item.paper_id === paperId);

  useEffect(() => {
    if (!paper) {
      return;
    }
    setDraftTitle(paper.title);
  }, [paper?.title]);

  if (!paperId) {
    return <ErrorState title="Missing paper ID" message="The route did not include a paper identifier." />;
  }

  if (papersQuery.isLoading) {
    return <p className="text-sm text-muted">Loading paper...</p>;
  }

  if (papersQuery.error) {
    return <ErrorState title="Unable to load paper" message={(papersQuery.error as Error).message} />;
  }
  if (!paper) {
    return <EmptyState title="Paper not found" description="This paper is not present in the local metadata list." />;
  }

  const noteAvailable = noteQuery.isSuccess && !!noteQuery.data?.content;

  return (
    <div className="space-y-6">
      <Link to="/papers" className="inline-flex items-center gap-2 text-sm text-muted hover:text-ink">
        <ArrowLeft className="h-4 w-4" aria-hidden="true" />
        Back to Papers
      </Link>

      <section className="rounded-md border border-line bg-panel p-5 shadow-panel">
        <div className="flex flex-col gap-4 xl:flex-row xl:items-start xl:justify-between">
          <div>
            <p className="text-xs font-medium uppercase text-muted">{paper.paper_id}</p>
            {isEditingTitle ? (
              <div className="mt-2 flex flex-col gap-2 sm:flex-row sm:items-center">
                <input
                  value={draftTitle}
                  onChange={(event) => setDraftTitle(event.target.value)}
                  className="w-full rounded-md border border-line bg-panel px-3 py-2 text-base text-ink"
                  placeholder="Enter paper title"
                />
                <div className="flex gap-2">
                  <button
                    type="button"
                    onClick={() => titleMutation.mutate(draftTitle)}
                    disabled={titleMutation.isPending || !draftTitle.trim()}
                    className="rounded-md bg-accent px-3 py-2 text-sm font-medium text-white disabled:opacity-60"
                  >
                    {titleMutation.isPending ? "Saving" : "Save"}
                  </button>
                  <button
                    type="button"
                    onClick={() => {
                      setDraftTitle(paper.title);
                      setIsEditingTitle(false);
                    }}
                    className="rounded-md border border-line px-3 py-2 text-sm font-medium text-muted hover:bg-surface"
                  >
                    Cancel
                  </button>
                </div>
              </div>
            ) : (
              <div className="mt-2 flex items-center gap-2">
                <h1 className="text-2xl font-semibold text-ink">{paper.title || "Untitled paper"}</h1>
                <button
                  type="button"
                  onClick={() => {
                    setDraftTitle(paper.title);
                    setIsEditingTitle(true);
                  }}
                  className="inline-flex items-center gap-1 rounded border border-line px-2 py-1 text-xs font-medium text-muted hover:bg-surface"
                >
                  <Pencil className="h-3.5 w-3.5" aria-hidden="true" />
                  Edit title
                </button>
              </div>
            )}
            <p className="mt-3 max-w-4xl text-sm leading-6 text-muted">{paper.abstract || "No abstract available."}</p>
          </div>
          <div className="flex flex-wrap gap-2">
            <button
              type="button"
              onClick={() => parseMutation.mutate()}
              disabled={parseMutation.isPending}
              className="rounded-md border border-line px-3 py-2 text-sm font-medium text-muted hover:bg-surface disabled:opacity-60"
            >
              {parseMutation.isPending ? "Parsing" : "Parse"}
            </button>
            <button
              type="button"
              onClick={() => indexMutation.mutate()}
              disabled={indexMutation.isPending}
              className="rounded-md border border-line px-3 py-2 text-sm font-medium text-muted hover:bg-surface disabled:opacity-60"
            >
              {indexMutation.isPending ? "Indexing" : "Index"}
            </button>
            <button
              type="button"
              onClick={refreshDetail}
              className="inline-flex items-center gap-2 rounded-md border border-line px-3 py-2 text-sm font-medium text-muted hover:bg-surface"
            >
              <RefreshCw className="h-4 w-4" aria-hidden="true" />
              Refresh
            </button>
          </div>
        </div>
      </section>

      {actionError && <ErrorState title="Paper action failed" message={actionError} />}
      <TaskStatusPanel task={latestTask} title="Latest index task" />

      <section className="grid gap-4 lg:grid-cols-3">
        <div className="rounded-md border border-line bg-panel p-4 shadow-panel">
          <p className="text-xs font-medium uppercase text-muted">Index status</p>
          {indexQuery.isLoading ? (
            <p className="mt-2 text-sm text-muted">Loading index status...</p>
          ) : indexQuery.error ? (
            <p className="mt-2 text-sm text-red-700">{(indexQuery.error as Error).message}</p>
          ) : (
            <div className="mt-3 space-y-2">
              <StatusBadge status={indexQuery.data?.indexed ? "completed" : "queued"} label={indexQuery.data?.indexed ? "indexed" : "not indexed"} />
              <p className="text-sm text-muted">{indexQuery.data?.chunk_count ?? 0} chunks</p>
            </div>
          )}
        </div>
        <div className="rounded-md border border-line bg-panel p-4 shadow-panel">
          <p className="text-xs font-medium uppercase text-muted">Sections</p>
          <p className="mt-2 text-sm text-muted">{indexQuery.data?.sections?.length ? indexQuery.data.sections.join(", ") : "No indexed sections yet."}</p>
        </div>
        <div className="rounded-md border border-line bg-panel p-4 shadow-panel">
          <p className="text-xs font-medium uppercase text-muted">Note</p>
          <div className="mt-3 flex flex-wrap gap-2">
            <StatusBadge status={noteAvailable ? "completed" : "queued"} label={noteAvailable ? "available" : "missing"} />
            <button
              type="button"
              onClick={() => noteMutation.mutate()}
              disabled={noteMutation.isPending}
              className="rounded border border-line px-2 py-1 text-xs font-medium text-muted hover:bg-surface disabled:opacity-60"
            >
              {noteMutation.isPending ? "Generating" : "Generate"}
            </button>
            {noteAvailable && (
              <button
                type="button"
                onClick={() => downloadMutation.mutate()}
                disabled={downloadMutation.isPending}
                className="inline-flex items-center gap-1 rounded border border-line px-2 py-1 text-xs font-medium text-muted hover:bg-surface disabled:opacity-60"
              >
                <Download className="h-3.5 w-3.5" aria-hidden="true" />
                {downloadMutation.isPending ? "Downloading" : "Download"}
              </button>
            )}
          </div>
        </div>
      </section>

      <section className="rounded-md border border-line bg-panel p-4 shadow-panel">
        <div className="flex items-center gap-2">
          <FileText className="h-4 w-4 text-accent" aria-hidden="true" />
          <h2 className="text-sm font-semibold text-ink">Note preview</h2>
        </div>
        {noteQuery.isLoading ? (
          <p className="mt-4 text-sm text-muted">Loading note...</p>
        ) : noteAvailable ? (
          <MarkdownContent
            content={noteQuery.data.content}
            className="mt-4 max-h-[32rem] overflow-auto rounded-md bg-surface p-4"
          />
        ) : (
          <div className="mt-4">
            <EmptyState title="No note yet" description="Generate a note to preview it here." />
          </div>
        )}
      </section>
    </div>
  );
}
