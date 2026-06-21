import { useEffect, useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import {
  getResearchRunDetail,
  getReport,
  type ResearchRunDetailResponse,
  type RunStatus,
} from "../../api/researchPipeline";
import { AgentTimeline } from "../../components/workflow/AgentTimeline";
import { CandidatePaperTable } from "../../components/workflow/CandidatePaperTable";
import { PaperCardPanel } from "../../components/workflow/PaperCardPanel";
import { HarnessSummary } from "../../components/workflow/HarnessSummary";
import { MarkdownReportPreview } from "../../components/workflow/MarkdownReportPreview";

const POLL_INTERVAL = 2000; // 2 seconds

const ACTIVE_STATUSES: RunStatus[] = ["queued", "running", "degraded"];

function shouldPoll(status: RunStatus): boolean {
  return ACTIVE_STATUSES.includes(status);
}

function formatTimestamp(timestamp: string | null): string {
  if (!timestamp) return "—";
  return new Date(timestamp).toLocaleString();
}

function getStatusColor(status: RunStatus): string {
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

export function RunDetailPage() {
  const { runId } = useParams<{ runId: string }>();
  const navigate = useNavigate();
  const [pollingEnabled, setPollingEnabled] = useState(true);

  const {
    data: run,
    isLoading,
    error,
  } = useQuery({
    queryKey: ["researchRun", runId],
    queryFn: () => getResearchRunDetail(runId!),
    enabled: !!runId,
    refetchInterval: pollingEnabled ? POLL_INTERVAL : false,
  });

  // Fetch report with claims and summary
  const { data: reportData } = useQuery({
    queryKey: ["researchReport", runId],
    queryFn: () => getReport(runId!),
    enabled: !!runId && run?.status === "completed" && !!run?.report,
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
        <AgentTimeline stages={run.stages} />
        <EventsLog run={run} />
        <CandidatePaperTable candidates={run.candidates} />
        <PaperCardPanel cards={run.cards} />
        {reportData && <HarnessSummary summary={reportData.summary} />}
        <MarkdownReportPreview markdown={run.report?.markdown || null} runId={run.run_id} />
      </div>
    </div>
  );
}
