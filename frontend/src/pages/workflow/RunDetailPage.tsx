import { useEffect, useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import {
  getResearchRunDetail,
  type ResearchRunDetailResponse,
  type RunStatus,
  type StageStatus,
  type StageName,
} from "../../api/researchPipeline";

const POLL_INTERVAL = 2000; // 2 seconds

const ACTIVE_STATUSES: RunStatus[] = ["queued", "running", "degraded"];

const STAGE_NAMES: StageName[] = ["planner", "retriever", "reader", "synthesis", "harness"];

function shouldPoll(status: RunStatus): boolean {
  return ACTIVE_STATUSES.includes(status);
}

function formatTimestamp(timestamp: string | null): string {
  if (!timestamp) return "—";
  return new Date(timestamp).toLocaleString();
}

function getStatusColor(status: RunStatus | StageStatus): string {
  switch (status) {
    case "completed":
      return "text-green-600";
    case "running":
      return "text-blue-600";
    case "queued":
      return "text-gray-500";
    case "failed":
      return "text-red-600";
    case "cancelled":
      return "text-gray-400";
    case "degraded":
      return "text-amber-600";
    default:
      return "text-gray-600";
  }
}

function StageProgressBar({ stage }: { stage: { stage: StageName; status: StageStatus; progress: number } }) {
  const statusColor = getStatusColor(stage.status);

  return (
    <div className="flex items-center gap-3">
      <div className="w-24 text-sm font-medium text-ink capitalize">{stage.stage}</div>
      <div className="flex-1 bg-gray-200 rounded-full h-2">
        <div
          className={`h-2 rounded-full ${
            stage.status === "completed"
              ? "bg-green-600"
              : stage.status === "running"
              ? "bg-blue-600"
              : stage.status === "failed"
              ? "bg-red-600"
              : stage.status === "degraded"
              ? "bg-amber-600"
              : "bg-gray-300"
          }`}
          style={{ width: `${stage.progress}%` }}
        />
      </div>
      <div className={`w-20 text-sm ${statusColor} capitalize`}>{stage.status}</div>
    </div>
  );
}

function RunHeader({ run }: { run: ResearchRunDetailResponse }) {
  const statusColor = getStatusColor(run.status);

  return (
    <div className="border-b border-line pb-6">
      <div className="flex items-start justify-between mb-4">
        <div className="flex-1">
          <h1 className="text-2xl font-semibold text-ink mb-2">{run.question}</h1>
          <div className="flex items-center gap-4 text-sm text-muted">
            <span>Run ID: {run.run_id}</span>
            <span className={`${statusColor} font-medium capitalize`}>{run.status}</span>
            <span>Source: {run.source_mode}</span>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-2 gap-4 text-sm">
        <div>
          <span className="text-muted">Created:</span>{" "}
          <span className="text-ink">{formatTimestamp(run.created_at)}</span>
        </div>
        <div>
          <span className="text-muted">Started:</span>{" "}
          <span className="text-ink">{formatTimestamp(run.started_at)}</span>
        </div>
        <div>
          <span className="text-muted">Completed:</span>{" "}
          <span className="text-ink">{formatTimestamp(run.completed_at)}</span>
        </div>
        <div>
          <span className="text-muted">Max Papers:</span>{" "}
          <span className="text-ink">{run.max_reader_papers}</span>
        </div>
      </div>

      {run.error && (
        <div className="mt-4 rounded-md border border-red-200 bg-red-50 px-4 py-3">
          <p className="text-sm text-red-600">{run.error}</p>
        </div>
      )}
    </div>
  );
}

function StageProgression({ run }: { run: ResearchRunDetailResponse }) {
  const stageMap = new Map(run.stages.map((s) => [s.stage, s]));

  return (
    <div className="border border-line rounded-lg p-4 bg-panel">
      <h2 className="text-lg font-semibold text-ink mb-4">Stage Progression</h2>
      <div className="space-y-3">
        {STAGE_NAMES.map((stageName) => {
          const stage = stageMap.get(stageName);
          if (stage) {
            return (
              <div key={stageName}>
                <StageProgressBar stage={stage} />
                {stage.error && (
                  <div className="ml-28 mt-1 text-sm text-red-600">{stage.error}</div>
                )}
                {stage.message && !stage.error && (
                  <div className="ml-28 mt-1 text-sm text-muted">{stage.message}</div>
                )}
              </div>
            );
          }
          return (
            <StageProgressBar
              key={stageName}
              stage={{ stage: stageName, status: "queued", progress: 0 }}
            />
          );
        })}
      </div>
    </div>
  );
}

function EventsLog({ run }: { run: ResearchRunDetailResponse }) {
  if (run.events.length === 0) {
    return null;
  }

  return (
    <div className="border border-line rounded-lg p-4 bg-panel">
      <h2 className="text-lg font-semibold text-ink mb-4">Events Log</h2>
      <div className="space-y-2 max-h-64 overflow-y-auto">
        {run.events.map((event) => (
          <div key={event.id} className="flex items-start gap-3 text-sm">
            <span className="text-muted whitespace-nowrap">
              {new Date(event.created_at).toLocaleTimeString()}
            </span>
            <span className="text-muted capitalize">{event.stage}</span>
            <span
              className={`capitalize ${
                event.level === "error"
                  ? "text-red-600"
                  : event.level === "warning"
                  ? "text-amber-600"
                  : "text-ink"
              }`}
            >
              {event.message}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}

function CandidatesTable({ run }: { run: ResearchRunDetailResponse }) {
  if (run.candidates.length === 0) {
    return null;
  }

  return (
    <div className="border border-line rounded-lg p-4 bg-panel">
      <h2 className="text-lg font-semibold text-ink mb-4">
        Paper Candidates ({run.candidates.length})
      </h2>
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead className="border-b border-line">
            <tr>
              <th className="text-left py-2 px-3 text-muted font-medium">Title</th>
              <th className="text-left py-2 px-3 text-muted font-medium">Authors</th>
              <th className="text-left py-2 px-3 text-muted font-medium">Year</th>
              <th className="text-left py-2 px-3 text-muted font-medium">Venue</th>
              <th className="text-left py-2 px-3 text-muted font-medium">Source</th>
              <th className="text-right py-2 px-3 text-muted font-medium">Relevance</th>
            </tr>
          </thead>
          <tbody>
            {run.candidates.map((candidate) => (
              <tr key={candidate.paper_id} className="border-b border-line last:border-b-0">
                <td className="py-2 px-3 text-ink">{candidate.title}</td>
                <td className="py-2 px-3 text-muted">
                  {candidate.authors.join(", ") || "—"}
                </td>
                <td className="py-2 px-3 text-muted">{candidate.year || "—"}</td>
                <td className="py-2 px-3 text-muted">{candidate.venue || "—"}</td>
                <td className="py-2 px-3 text-muted capitalize">{candidate.source}</td>
                <td className="py-2 px-3 text-muted text-right">
                  {candidate.relevance_score != null
                    ? candidate.relevance_score.toFixed(2)
                    : "—"}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function PaperCardsList({ run }: { run: ResearchRunDetailResponse }) {
  if (run.cards.length === 0) {
    return null;
  }

  return (
    <div className="border border-line rounded-lg p-4 bg-panel">
      <h2 className="text-lg font-semibold text-ink mb-4">
        Paper Cards ({run.cards.length})
      </h2>
      <div className="space-y-4">
        {run.cards.map((card) => (
          <div key={card.paper_id} className="border border-line rounded-lg p-4 bg-white">
            <div className="flex items-start justify-between mb-2">
              <h3 className="text-base font-semibold text-ink">{card.title}</h3>
              <span className={`text-sm ${getStatusColor(card.status)} capitalize`}>
                {card.status}
              </span>
            </div>

            {card.research_problem && (
              <div className="mb-2">
                <span className="text-sm font-medium text-muted">Problem: </span>
                <span className="text-sm text-ink">{card.research_problem}</span>
              </div>
            )}

            {card.method && (
              <div className="mb-2">
                <span className="text-sm font-medium text-muted">Method: </span>
                <span className="text-sm text-ink">{card.method}</span>
              </div>
            )}

            {card.key_results.length > 0 && (
              <div className="mb-2">
                <span className="text-sm font-medium text-muted">Key Results: </span>
                <span className="text-sm text-ink">{card.key_results.join("; ")}</span>
              </div>
            )}

            {card.error && (
              <div className="mt-2 text-sm text-red-600">Error: {card.error}</div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}

function ReportPreview({ run }: { run: ResearchRunDetailResponse }) {
  if (!run.report) {
    return null;
  }

  return (
    <div className="border border-line rounded-lg p-4 bg-panel">
      <h2 className="text-lg font-semibold text-ink mb-4">Report Preview</h2>
      <div className="prose prose-sm max-w-none">
        <pre className="whitespace-pre-wrap text-sm text-ink bg-white border border-line rounded p-4 overflow-x-auto">
          {run.report.markdown}
        </pre>
      </div>
    </div>
  );
}

export function RunDetailPage() {
  const { runId } = useParams<{ runId: string }>();
  const navigate = useNavigate();
  const [pollingEnabled, setPollingEnabled] = useState(true);

  const {
    data: run,
    isLoading,
    error,
    refetch,
  } = useQuery({
    queryKey: ["researchRun", runId],
    queryFn: () => getResearchRunDetail(runId!),
    enabled: !!runId,
    refetchInterval: pollingEnabled ? POLL_INTERVAL : false,
  });

  // Update polling based on run status
  useEffect(() => {
    if (run) {
      const shouldContinuePolling = shouldPoll(run.status);
      if (pollingEnabled !== shouldContinuePolling) {
        setPollingEnabled(shouldContinuePolling);
      }
    }
  }, [run, pollingEnabled]);

  if (isLoading) {
    return (
      <div className="p-6">
        <p className="text-muted">Loading run details...</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="p-6">
        <div className="rounded-md border border-red-200 bg-red-50 px-4 py-3">
          <p className="text-sm text-red-600">
            {error instanceof Error ? error.message : "Failed to load run details"}
          </p>
        </div>
        <button
          onClick={() => navigate("/workflow")}
          className="mt-4 text-sm text-accent hover:text-accent-hover"
        >
          ← Back to Workflow
        </button>
      </div>
    );
  }

  if (!run) {
    return (
      <div className="p-6">
        <p className="text-muted">Run not found</p>
      </div>
    );
  }

  return (
    <div className="p-6">
      <div className="mb-6">
        <button
          onClick={() => navigate("/workflow")}
          className="text-sm text-muted hover:text-ink mb-4"
        >
          ← Back to Workflow
        </button>
      </div>

      <div className="space-y-6">
        <RunHeader run={run} />
        <StageProgression run={run} />
        <EventsLog run={run} />
        <CandidatesTable run={run} />
        <PaperCardsList run={run} />
        <ReportPreview run={run} />
      </div>
    </div>
  );
}
