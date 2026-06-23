import { useState } from "react";
import { MarkdownContent } from "../common/MarkdownContent";

export interface MarkdownReportPreviewProps {
  markdown: string | null;
  runId: string;
}

type CopyStatus = "idle" | "copied" | "failed";

function isFallbackReport(markdown: string): boolean {
  return markdown.includes("[自动综合不可用]") || markdown.includes("LLM 不可用");
}

async function copyMarkdownToClipboard(markdown: string): Promise<void> {
  try {
    await navigator.clipboard.writeText(markdown);
    return;
  } catch {
    // Some embedded browsers deny navigator.clipboard writes even after a user click.
  }

  const textarea = document.createElement("textarea");
  textarea.value = markdown;
  textarea.setAttribute("readonly", "");
  textarea.style.position = "fixed";
  textarea.style.top = "-9999px";
  textarea.style.left = "-9999px";
  document.body.appendChild(textarea);

  try {
    textarea.focus();
    textarea.select();
    const copied = document.execCommand("copy");
    if (!copied) {
      throw new Error("copy command returned false");
    }
  } finally {
    document.body.removeChild(textarea);
  }
}

export function MarkdownReportPreview({ markdown, runId }: MarkdownReportPreviewProps) {
  const [copyStatus, setCopyStatus] = useState<CopyStatus>("idle");

  if (!markdown || markdown.trim() === "") {
    return null;
  }

  const fallbackReport = isFallbackReport(markdown);

  const handleCopy = async () => {
    try {
      await copyMarkdownToClipboard(markdown);
      setCopyStatus("copied");
      setTimeout(() => setCopyStatus("idle"), 2000);
    } catch (err) {
      console.error("Failed to copy:", err);
      setCopyStatus("failed");
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
            {copyStatus === "copied" ? "Copied!" : "Copy"}
          </button>
          <button
            onClick={handleDownload}
            className="px-3 py-1 text-sm border border-line rounded hover:bg-gray-50 transition-colors"
          >
            Download
          </button>
        </div>
      </div>
      {fallbackReport && (
        <div className="mb-4 rounded-md border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800">
          自动综合未生成完整自然语言综述：后端没有可用的 LLM synthesis 结果，已回退为基于
          PaperCards 的确定性骨架报告。
        </div>
      )}
      {copyStatus === "failed" && (
        <div className="mb-4 rounded-md border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
          Copy failed because the browser denied clipboard access. Use Download as a fallback.
        </div>
      )}
      <MarkdownContent
        content={markdown}
        className="bg-white border border-line rounded p-4"
      />
    </div>
  );
}
