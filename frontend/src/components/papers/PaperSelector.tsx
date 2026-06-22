import type { PaperListItem } from "../../api/types";

interface PaperSelectorProps {
  papers: PaperListItem[];
  value: string;
  onChange: (paperId: string) => void;
  label?: string;
}

export function PaperSelector({ papers, value, onChange, label = "Paper" }: PaperSelectorProps) {
  return (
    <label className="block">
      <span className="text-xs font-medium uppercase text-muted">{label}</span>
      <select
        value={value}
        onChange={(event) => onChange(event.target.value)}
        className="mt-1 w-full rounded-md border border-line bg-panel px-3 py-2 text-sm text-ink"
      >
        <option value="">Select a paper</option>
        {papers.map((paper) => (
          <option key={paper.paper_id} value={paper.paper_id}>
            {paper.title || paper.paper_id}
          </option>
        ))}
      </select>
    </label>
  );
}
