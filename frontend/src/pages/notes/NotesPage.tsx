import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Download, RefreshCw } from "lucide-react";
import { getPaperNote, generatePaperNote, getPaperNoteDownloadUrl } from "../../api/notes";
import { getPapers } from "../../api/papers";
import { submitNoteTask } from "../../api/tasks";
import type { TaskStatus } from "../../api/types";
import { EmptyState } from "../../components/empty-state/EmptyState";
import { ErrorState } from "../../components/error-state/ErrorState";
import { PaperSelector } from "../../components/papers/PaperSelector";
import { TaskStatusPanel } from "../../components/tasks/TaskStatusPanel";

export function NotesPage() {
  const queryClient = useQueryClient();
  const [selectedPaperId, setSelectedPaperId] = useState("");
  const [latestTask, setLatestTask] = useState<TaskStatus | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);

  const papersQuery = useQuery({
    queryKey: ["papers"],
    queryFn: getPapers
  });

  const noteQuery = useQuery({
    queryKey: ["paper-note", selectedPaperId],
    queryFn: () => getPaperNote(selectedPaperId),
    enabled: !!selectedPaperId,
    retry: false
  });

  const refreshNote = () => {
    if (selectedPaperId) {
      void queryClient.invalidateQueries({ queryKey: ["paper-note", selectedPaperId] });
    }
  };

  const generateMutation = useMutation({
    mutationFn: generatePaperNote,
    onSuccess: () => {
      setActionError(null);
      refreshNote();
    },
    onError: (error) => setActionError(error instanceof Error ? error.message : "Note generation failed")
  });

  const taskMutation = useMutation({
    mutationFn: submitNoteTask,
    onSuccess: (task) => {
      setLatestTask(task);
      setActionError(null);
    },
    onError: (error) => setActionError(error instanceof Error ? error.message : "Note task failed")
  });

  if (papersQuery.isLoading) {
    return <p className="text-sm text-muted">Loading papers...</p>;
  }

  if (papersQuery.error) {
    return <ErrorState title="Unable to load papers" message={(papersQuery.error as Error).message} />;
  }

  const papers = papersQuery.data?.papers ?? [];

  return (
    <div className="space-y-6">
      <section className="flex flex-col gap-4 xl:flex-row xl:items-end xl:justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-ink">Notes</h1>
          <p className="mt-2 max-w-3xl text-sm leading-6 text-muted">
            Generate, read, preview, and download Markdown notes for local papers.
          </p>
        </div>
        <div className="w-full max-w-xl rounded-md border border-line bg-panel p-4">
          <PaperSelector
            papers={papers}
            value={selectedPaperId}
            onChange={(paperId) => {
              setSelectedPaperId(paperId);
              setActionError(null);
              setLatestTask(null);
            }}
            label="Select paper"
          />
        </div>
      </section>

      {papers.length === 0 && <EmptyState title="No papers available" description="Upload papers before generating notes." />}
      {actionError && <ErrorState title="Note action failed" message={actionError} />}
      <TaskStatusPanel task={latestTask} title="Latest note task" />

      {selectedPaperId ? (
        <section className="rounded-md border border-line bg-panel shadow-panel">
          <div className="flex flex-col gap-3 border-b border-line p-4 md:flex-row md:items-center md:justify-between">
            <div>
              <h2 className="text-sm font-semibold text-ink">Note preview</h2>
              <p className="mt-1 text-xs text-muted">{selectedPaperId}</p>
            </div>
            <div className="flex flex-wrap gap-2">
              <button
                type="button"
                onClick={() => generateMutation.mutate(selectedPaperId)}
                disabled={generateMutation.isPending}
                className="rounded-md bg-accent px-3 py-2 text-sm font-medium text-white hover:bg-accent-hover disabled:opacity-60"
              >
                {generateMutation.isPending ? "Generating" : "Generate now"}
              </button>
              <button
                type="button"
                onClick={() => taskMutation.mutate(selectedPaperId)}
                disabled={taskMutation.isPending}
                className="rounded-md border border-line px-3 py-2 text-sm font-medium text-muted hover:bg-surface disabled:opacity-60"
              >
                {taskMutation.isPending ? "Submitting" : "Submit task"}
              </button>
              <button
                type="button"
                onClick={refreshNote}
                className="inline-flex items-center gap-2 rounded-md border border-line px-3 py-2 text-sm font-medium text-muted hover:bg-surface"
              >
                <RefreshCw className="h-4 w-4" aria-hidden="true" />
                Refresh
              </button>
              {noteQuery.isSuccess && (
                <a
                  href={getPaperNoteDownloadUrl(selectedPaperId)}
                  className="inline-flex items-center gap-2 rounded-md border border-line px-3 py-2 text-sm font-medium text-muted hover:bg-surface"
                >
                  <Download className="h-4 w-4" aria-hidden="true" />
                  Download
                </a>
              )}
            </div>
          </div>

          <div className="p-4">
            {noteQuery.isLoading ? (
              <p className="text-sm text-muted">Loading note...</p>
            ) : noteQuery.isSuccess ? (
              <pre className="max-h-[36rem] overflow-auto whitespace-pre-wrap rounded-md bg-surface p-4 text-sm leading-6 text-ink">
                {noteQuery.data.content}
              </pre>
            ) : (
              <EmptyState title="No note found" description="Generate a note synchronously or submit a background note task." />
            )}
          </div>
        </section>
      ) : (
        papers.length > 0 && <EmptyState title="Select a paper" description="Choose a paper to view or generate its note." />
      )}
    </div>
  );
}
