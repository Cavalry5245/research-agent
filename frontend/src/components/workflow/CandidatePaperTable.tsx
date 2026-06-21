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
              <th className="text-left py-2 px-3 text-muted font-medium">Authors</th>
              <th className="text-left py-2 px-3 text-muted font-medium">Venue</th>
              <th className="text-left py-2 px-3 text-muted font-medium">Year</th>
            </tr>
          </thead>
          <tbody>
            {candidates.map((candidate) => (
              <tr key={candidate.paper_id} className="border-b border-line last:border-b-0">
                <td className="py-2 px-3 text-muted capitalize">{candidate.source}</td>
                <td className="py-2 px-3 text-ink">{candidate.title}</td>
                <td className="py-2 px-3 text-muted">
                  {candidate.authors.length > 0 ? candidate.authors.join(", ") : "—"}
                </td>
                <td className="py-2 px-3 text-muted">{candidate.venue || "—"}</td>
                <td className="py-2 px-3 text-muted">{candidate.year || "—"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
