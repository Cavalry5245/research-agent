import { useMemo, useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { useQuery } from "@tanstack/react-query";
import { comparePapers } from "../../api/compare";
import { getPapers } from "../../api/papers";
import { submitCompareTask } from "../../api/tasks";
import type { TaskStatus } from "../../api/types";
import { EmptyState } from "../../components/empty-state/EmptyState";
import { ErrorState } from "../../components/error-state/ErrorState";
import { TaskStatusPanel } from "../../components/tasks/TaskStatusPanel";

export function ComparePage() {
  const [selectedIds, setSelectedIds] = useState<string[]>([]);
  const [latestTask, setLatestTask] = useState<TaskStatus | null>(null);

  const papersQuery = useQuery({
    queryKey: ["papers"],
    queryFn: getPapers
  });

  const compareMutation = useMutation({
    mutationFn: comparePapers
  });

  const taskMutation = useMutation({
    mutationFn: submitCompareTask,
    onSuccess: setLatestTask
  });

  const selectedCount = selectedIds.length;
  const validationMessage = useMemo(() => {
    if (selectedCount < 2) return "Select at least 2 papers.";
    if (selectedCount > 5) return "Select no more than 5 papers.";
    return "";
  }, [selectedCount]);

  if (papersQuery.isLoading) {
    return <p className="text-sm text-muted">Loading papers...</p>;
  }

  if (papersQuery.error) {
    return <ErrorState title="Unable to load papers" message={(papersQuery.error as Error).message} />;
  }

  const papers = papersQuery.data?.papers ?? [];
  const canRun = selectedCount >= 2 && selectedCount <= 5;

  return (
    <div className="space-y-6">
      <section>
        <h1 className="text-2xl font-semibold text-ink">Compare</h1>
        <p className="mt-2 max-w-3xl text-sm leading-6 text-muted">
          Select two to five papers, run a structured comparison, and preview the Markdown output.
        </p>
      </section>

      {papers.length === 0 ? (
        <EmptyState title="No papers available" description="Upload papers before running a comparison." />
      ) : (
        <section className="grid gap-4 xl:grid-cols-[24rem_1fr]">
          <div className="rounded-md border border-line bg-panel p-4 shadow-panel">
            <h2 className="text-sm font-semibold text-ink">Paper selection</h2>
            <p className="mt-1 text-xs text-muted">{selectedCount} selected</p>
            <div className="mt-4 max-h-[32rem] space-y-2 overflow-auto">
              {papers.map((paper) => (
                <label key={paper.paper_id} className="flex items-start gap-3 rounded-md border border-line p-3 hover:bg-surface">
                  <input
                    type="checkbox"
                    className="mt-1"
                    checked={selectedIds.includes(paper.paper_id)}
                    onChange={(event) => {
                      setSelectedIds((current) =>
                        event.target.checked
                          ? [...current, paper.paper_id]
                          : current.filter((paperId) => paperId !== paper.paper_id)
                      );
                    }}
                  />
                  <span>
                    <span className="block text-sm font-medium text-ink">{paper.title || paper.paper_id}</span>
                    <span className="mt-1 line-clamp-2 block text-xs text-muted">{paper.abstract || paper.paper_id}</span>
                  </span>
                </label>
              ))}
            </div>
            {validationMessage && <p className="mt-3 text-sm text-amber-700">{validationMessage}</p>}
            <div className="mt-4 flex flex-col gap-2">
              <button
                type="button"
                disabled={!canRun || compareMutation.isPending}
                onClick={() => compareMutation.mutate(selectedIds)}
                className="rounded-md bg-accent px-4 py-2 text-sm font-medium text-white hover:bg-accent-hover disabled:opacity-60"
              >
                {compareMutation.isPending ? "Comparing" : "Compare now"}
              </button>
              <button
                type="button"
                disabled={!canRun || taskMutation.isPending}
                onClick={() => taskMutation.mutate(selectedIds)}
                className="rounded-md border border-line px-4 py-2 text-sm font-medium text-muted hover:bg-surface disabled:opacity-60"
              >
                {taskMutation.isPending ? "Submitting" : "Submit compare task"}
              </button>
            </div>
          </div>

          <div className="space-y-4">
            {compareMutation.error && <ErrorState title="Comparison failed" message={(compareMutation.error as Error).message} />}
            {taskMutation.error && <ErrorState title="Compare task failed" message={(taskMutation.error as Error).message} />}
            <TaskStatusPanel task={latestTask} title="Latest compare task" />
            {compareMutation.data ? (
              <section className="rounded-md border border-line bg-panel p-4 shadow-panel">
                <div className="flex flex-col gap-2 md:flex-row md:items-center md:justify-between">
                  <div>
                    <h2 className="text-sm font-semibold text-ink">Comparison preview</h2>
                    <p className="mt-1 text-xs text-muted">{compareMutation.data.output_path}</p>
                  </div>
                  <span className="text-xs font-medium uppercase text-muted">{compareMutation.data.status}</span>
                </div>
                <pre className="mt-4 max-h-[40rem] overflow-auto whitespace-pre-wrap rounded-md bg-surface p-4 text-sm leading-6 text-ink">
                  {compareMutation.data.content}
                </pre>
              </section>
            ) : (
              <EmptyState title="No comparison yet" description="Run a comparison to preview the Markdown output." />
            )}
          </div>
        </section>
      )}
    </div>
  );
}
