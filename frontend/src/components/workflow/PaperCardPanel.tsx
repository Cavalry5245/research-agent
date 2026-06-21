import type { PaperCard, StageStatus } from "../../api/researchPipeline";

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

export interface PaperCardPanelProps {
  cards: PaperCard[];
}

export function PaperCardPanel({ cards }: PaperCardPanelProps) {
  if (cards.length === 0) {
    return null;
  }

  return (
    <div className="border border-line rounded-lg p-4 bg-panel">
      <h2 className="text-lg font-semibold text-ink mb-4">
        Paper Cards ({cards.length})
      </h2>
      <div className="space-y-4">
        {cards.map((card) => (
          <div key={card.paper_id} className="border border-line rounded-lg p-4 bg-white">
            <div className="flex items-start justify-between mb-3">
              <h3 className="text-base font-semibold text-ink flex-1">{card.title}</h3>
              <span className={`text-sm ${getStatusColor(card.status)} capitalize ml-3`}>
                {card.status}
              </span>
            </div>

            <div className="grid grid-cols-1 gap-2 text-sm">
              <div>
                <span className="font-medium text-muted">Extraction Mode: </span>
                <span className="text-ink">{card.extraction_mode}</span>
              </div>

              {card.method && (
                <div>
                  <span className="font-medium text-muted">Method: </span>
                  <span className="text-ink">{card.method}</span>
                </div>
              )}

              {card.datasets.length > 0 && (
                <div>
                  <span className="font-medium text-muted">Datasets: </span>
                  <span className="text-ink">{card.datasets.join(", ")}</span>
                </div>
              )}

              {card.metrics.length > 0 && (
                <div>
                  <span className="font-medium text-muted">Metrics: </span>
                  <span className="text-ink">{card.metrics.join(", ")}</span>
                </div>
              )}

              {card.limitations.length > 0 && (
                <div>
                  <span className="font-medium text-muted">Limitations: </span>
                  <span className="text-ink">{card.limitations.join("; ")}</span>
                </div>
              )}
            </div>

            {card.error && (
              <div className="mt-2 text-sm text-red-600">Error: {card.error}</div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
