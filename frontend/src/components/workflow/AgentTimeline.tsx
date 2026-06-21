import type { ResearchStage, StageName, StageStatus } from "../../api/researchPipeline";

const STAGE_NAMES: StageName[] = ["planner", "retriever", "reader", "synthesis", "harness"];

function getStatusColor(status: StageStatus): string {
  switch (status) {
    case "completed":
      return "text-green-600";
    case "running":
      return "text-blue-600";
    case "queued":
      return "text-gray-500";
    case "failed":
      return "text-red-600";
    case "degraded":
      return "text-amber-600";
    default:
      return "text-gray-600";
  }
}

function getProgressBarColor(status: StageStatus): string {
  switch (status) {
    case "completed":
      return "bg-green-600";
    case "running":
      return "bg-blue-600";
    case "failed":
      return "bg-red-600";
    case "degraded":
      return "bg-amber-600";
    default:
      return "bg-gray-300";
  }
}

interface StageProgressBarProps {
  stage: {
    stage: StageName;
    status: StageStatus;
    progress: number;
  };
}

function StageProgressBar({ stage }: StageProgressBarProps) {
  const statusColor = getStatusColor(stage.status);
  const progressColor = getProgressBarColor(stage.status);

  return (
    <div className="flex items-center gap-3">
      <div className="w-24 text-sm font-medium text-ink capitalize">{stage.stage}</div>
      <div className="flex-1 bg-gray-200 rounded-full h-2">
        <div
          className={`h-2 rounded-full ${progressColor}`}
          style={{ width: `${stage.progress}%` }}
        />
      </div>
      <div className={`w-20 text-sm ${statusColor} capitalize`}>{stage.status}</div>
    </div>
  );
}

export interface AgentTimelineProps {
  stages: ResearchStage[];
}

export function AgentTimeline({ stages }: AgentTimelineProps) {
  const stageMap = new Map(stages.map((s) => [s.stage, s]));

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
