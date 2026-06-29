import { Search } from "lucide-react";
import { useMemo, useState } from "react";
import type { PaperListItem } from "../../api/types";

interface ResearchSetPaperPickerProps {
  papers: PaperListItem[];
  selectedPaperIds: string[];
  onToggle: (paperId: string) => void;
}

export function ResearchSetPaperPicker({ papers, selectedPaperIds, onToggle }: ResearchSetPaperPickerProps) {
  const [query, setQuery] = useState("");
  const selected = new Set(selectedPaperIds);
  const normalizedQuery = query.trim().toLowerCase();
  const filteredPapers = useMemo(() => {
    if (!normalizedQuery) return papers;
    return papers.filter((paper) => {
      const title = paper.title.toLowerCase();
      const paperId = paper.paper_id.toLowerCase();
      return title.includes(normalizedQuery) || paperId.includes(normalizedQuery);
    });
  }, [normalizedQuery, papers]);

  return (
    <div className="min-w-0 space-y-3">
      <label className="block">
        <span className="text-xs font-medium uppercase text-muted">Add papers</span>
        <div className="mt-1 flex items-center gap-2 rounded-md border border-line bg-white px-3 py-2">
          <Search className="h-4 w-4 text-muted" aria-hidden="true" />
          <input
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            className="min-w-0 flex-1 border-0 bg-transparent p-0 text-sm text-ink outline-none placeholder:text-muted"
            placeholder="Search by title or ID"
          />
        </div>
      </label>

      <div className="max-h-44 overflow-y-auto rounded-md border border-line bg-white">
        {filteredPapers.length === 0 ? (
          <p className="px-3 py-4 text-sm text-muted">No matching papers.</p>
        ) : (
          filteredPapers.map((paper) => (
            <label
              key={paper.paper_id}
              className="flex cursor-pointer items-start gap-3 border-b border-line px-3 py-2 last:border-b-0 hover:bg-surface"
            >
              <input
                type="checkbox"
                checked={selected.has(paper.paper_id)}
                onChange={() => onToggle(paper.paper_id)}
                className="mt-1 h-4 w-4 rounded border-line text-accent"
              />
              <span className="min-w-0">
                <span className="block truncate text-sm font-medium text-ink">{paper.title || paper.paper_id}</span>
                <span className="block truncate text-xs text-muted">{paper.paper_id}</span>
              </span>
            </label>
          ))
        )}
      </div>
    </div>
  );
}
