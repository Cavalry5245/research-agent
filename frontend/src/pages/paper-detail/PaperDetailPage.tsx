import { useParams } from "react-router-dom";
import { QueuedSlicePage } from "../QueuedSlicePage";

export function PaperDetailPage() {
  const { paperId } = useParams();
  return (
    <QueuedSlicePage
      title={`Paper Detail${paperId ? `: ${paperId}` : ""}`}
      description="Next migration slice: parsed metadata, note status, index status, sections, source chunks, and paper-scoped QA."
    />
  );
}
