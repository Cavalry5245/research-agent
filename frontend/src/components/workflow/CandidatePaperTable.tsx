import type { PaperCandidate } from "../../api/researchPipeline";

export interface CandidatePaperTableProps {
  candidates: PaperCandidate[];
}

export function CandidatePaperTable({ candidates }: CandidatePaperTableProps) {
  if (candidates.length === 0) {
    return null;
  }

  return (
    <div className="border border-line rounded-lg p-4 bg-panel">
      <h2 className="text-lg font-semibold text-ink mb-4">
        Paper Candidates ({candidates.length})
      </h2>
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead className="border-b border-line">
            <tr>
              <th className="text-left py-2 px-3 text-muted font-medium">Source</th>
              <th className="text-left py-2 px-3 text-muted font-medium">Title</th>
              <th className="text-left py-2 px-3 text-muted font-medium">Year</th>
              <th className="text-left py-2 px-3 text-muted font-medium">Selected</th>
            </tr>
          </thead>
          <tbody>
            {candidates.map((candidate) => (
              <tr key={candidate.paper_id} className="border-b border-line last:border-b-0">
                <td className="py-2 px-3 text-muted capitalize">{candidate.source}</td>
                <td className="py-2 px-3 text-ink">{candidate.title}</td>
                <td className="py-2 px-3 text-muted">{candidate.year || "—"}</td>
                <td className="py-2 px-3 text-muted">
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
