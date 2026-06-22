import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { MarkdownReportPreview } from "./MarkdownReportPreview";

// Mock navigator.clipboard
Object.assign(navigator, {
  clipboard: {
    writeText: vi.fn(() => Promise.resolve()),
  },
});

// Mock URL.createObjectURL and URL.revokeObjectURL
global.URL.createObjectURL = vi.fn(() => "mock-url");
global.URL.revokeObjectURL = vi.fn();

// Mock document.createElement for download test
const mockCreateElement = vi.fn();
const originalCreateElement = document.createElement.bind(document);

beforeEach(() => {
  vi.clearAllMocks();
  document.execCommand = vi.fn(() => true);
  // Reset createElement to work normally but track anchor element creation
  document.createElement = ((tagName: string) => {
    const element = originalCreateElement(tagName);
    if (tagName === "a") {
      element.click = vi.fn();
      mockCreateElement(tagName);
    }
    return element;
  }) as any;
});

describe("MarkdownReportPreview", () => {
  const sampleMarkdown = `# Research Report

## Introduction
This is a test report.

## Methods
We used approach X.`;

  it("renders nothing when markdown is null", () => {
    const { container } = render(<MarkdownReportPreview markdown={null} runId="test-run" />);
    expect(container.firstChild).toBeNull();
  });

  it("renders nothing when markdown is empty", () => {
    const { container } = render(<MarkdownReportPreview markdown="" runId="test-run" />);
    expect(container.firstChild).toBeNull();
  });

  it("displays markdown content", () => {
    render(<MarkdownReportPreview markdown={sampleMarkdown} runId="test-run" />);

    expect(screen.getByText(/Research Report/i)).toBeInTheDocument();
    expect(screen.getByText(/This is a test report/i)).toBeInTheDocument();
  });

  it("renders copy button", () => {
    render(<MarkdownReportPreview markdown={sampleMarkdown} runId="test-run" />);

    const copyButton = screen.getByRole("button", { name: /copy/i });
    expect(copyButton).toBeInTheDocument();
  });

  it("renders download button", () => {
    render(<MarkdownReportPreview markdown={sampleMarkdown} runId="test-run" />);

    const downloadButton = screen.getByRole("button", { name: /download/i });
    expect(downloadButton).toBeInTheDocument();
  });

  it("copies markdown to clipboard when copy button is clicked", async () => {
    const writeTextMock = vi.spyOn(navigator.clipboard, "writeText");

    render(<MarkdownReportPreview markdown={sampleMarkdown} runId="test-run" />);

    const copyButton = screen.getByRole("button", { name: /copy/i });
    fireEvent.click(copyButton);

    await waitFor(() => {
      expect(writeTextMock).toHaveBeenCalledWith(sampleMarkdown);
    });
  });

  it("shows feedback after copying", async () => {
    render(<MarkdownReportPreview markdown={sampleMarkdown} runId="test-run" />);

    const copyButton = screen.getByRole("button", { name: /copy/i });
    fireEvent.click(copyButton);

    // Should show "Copied!" text
    await waitFor(() => {
      expect(screen.getByText(/copied/i)).toBeInTheDocument();
    });
  });

  it("falls back when clipboard write permission is denied", async () => {
    const writeTextMock = vi
      .spyOn(navigator.clipboard, "writeText")
      .mockRejectedValueOnce(new DOMException("Write permission denied", "NotAllowedError"));
    const execCommandMock = vi.spyOn(document, "execCommand").mockReturnValueOnce(true);

    render(<MarkdownReportPreview markdown={sampleMarkdown} runId="test-run" />);

    const copyButton = screen.getByRole("button", { name: /copy/i });
    fireEvent.click(copyButton);

    await waitFor(() => {
      expect(writeTextMock).toHaveBeenCalledWith(sampleMarkdown);
      expect(execCommandMock).toHaveBeenCalledWith("copy");
      expect(screen.getByText(/copied/i)).toBeInTheDocument();
    });
  });

  it("shows copy failure feedback when all copy methods fail", async () => {
    vi.spyOn(navigator.clipboard, "writeText").mockRejectedValueOnce(
      new DOMException("Write permission denied", "NotAllowedError"),
    );
    vi.spyOn(document, "execCommand").mockReturnValueOnce(false);

    render(<MarkdownReportPreview markdown={sampleMarkdown} runId="test-run" />);

    const copyButton = screen.getByRole("button", { name: /copy/i });
    fireEvent.click(copyButton);

    await waitFor(() => {
      expect(screen.getByText(/browser denied clipboard access/i)).toBeInTheDocument();
    });
  });

  it("explains fallback reports generated without LLM synthesis", () => {
    const fallbackMarkdown = `# Research Report

> **注意**: 本报告由自动骨架生成，LLM 不可用。需要人工综合完成各章节内容。

[自动综合不可用] 需要人工总结。`;

    render(<MarkdownReportPreview markdown={fallbackMarkdown} runId="test-run" />);

    expect(screen.getByText(/后端没有可用的 LLM synthesis 结果/i)).toBeInTheDocument();
  });

  it("creates download link with correct filename", () => {
    render(<MarkdownReportPreview markdown={sampleMarkdown} runId="test-123" />);

    const downloadButton = screen.getByRole("button", { name: /download/i });
    expect(downloadButton).toBeInTheDocument();

    // Verify download functionality is triggered when clicked
    fireEvent.click(downloadButton);
    expect(mockCreateElement).toHaveBeenCalledWith("a");
  });

  it("preserves markdown formatting in preview", () => {
    const formattedMarkdown = `# Title
## Subtitle

**Bold text** and *italic text*.

- Item 1
- Item 2`;

    render(<MarkdownReportPreview markdown={formattedMarkdown} runId="test-run" />);

    const preElement = screen.getByText(/Bold text/i).closest("pre");
    expect(preElement).toBeInTheDocument();
  });
});
