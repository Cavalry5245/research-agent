import { useState } from "react";

export interface MarkdownReportPreviewProps {
  markdown: string | null;
  runId: string;
}

export function MarkdownReportPreview({ markdown, runId }: MarkdownReportPreviewProps) {
  const [copied, setCopied] = useState(false);

  if (!markdown) {
    return null;
  }

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(markdown);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch (err) {
      console.error("Failed to copy:", err);
    }
  };

  const handleDownload = () => {
    const blob = new Blob([markdown], { type: "text/markdown" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `report-${runId}.md`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  };

  return (
    <div className="border border-line rounded-lg p-4 bg-panel">
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-lg font-semibold text-ink">Report Preview</h2>
        <div className="flex gap-2">
          <button
            onClick={handleCopy}
            className="px-3 py-1 text-sm border border-line rounded hover:bg-gray-50 transition-colors"
          >
            {copied ? "Copied!" : "Copy"}
          </button>
          <button
            onClick={handleDownload}
            className="px-3 py-1 text-sm border border-line rounded hover:bg-gray-50 transition-colors"
          >
            Download
          </button>
        </div>
      </div>
      <div className="prose prose-sm max-w-none">
        <pre className="whitespace-pre-wrap text-sm text-ink bg-white border border-line rounded p-4 overflow-x-auto">
          {markdown}
        </pre>
      </div>
    </div>
  );
}
