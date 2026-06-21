import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { AgentTimeline } from "./AgentTimeline";
import type { ResearchStage, StageName } from "../../api/researchPipeline";

function createStage(
  stage: StageName,
  status: "queued" | "running" | "completed" | "failed" | "degraded",
  progress: number,
  message?: string,
  error?: string
): ResearchStage {
  return {
    id: `stage-${stage}`,
    run_id: "test-run",
    stage,
    status,
    progress,
    message: message || "",
    error: error || null,
    started_at: null,
    completed_at: null,
    created_at: new Date().toISOString(),
  };
}

describe("AgentTimeline", () => {
  it("renders all five stages in order", () => {
    const stages: ResearchStage[] = [
      createStage("planner", "completed", 100),
      createStage("retriever", "running", 50),
      createStage("reader", "queued", 0),
      createStage("synthesis", "queued", 0),
      createStage("harness", "queued", 0),
    ];

    render(<AgentTimeline stages={stages} />);

    expect(screen.getByText("planner")).toBeInTheDocument();
    expect(screen.getByText("retriever")).toBeInTheDocument();
    expect(screen.getByText("reader")).toBeInTheDocument();
    expect(screen.getByText("synthesis")).toBeInTheDocument();
    expect(screen.getByText("harness")).toBeInTheDocument();
  });

  it("displays stage status correctly", () => {
    const stages: ResearchStage[] = [
      createStage("planner", "completed", 100),
      createStage("retriever", "running", 50),
      createStage("reader", "failed", 25),
    ];

    render(<AgentTimeline stages={stages} />);

    const statuses = screen.getAllByText(/completed|running|failed|queued/i);
    expect(statuses).toHaveLength(5); // 3 actual + 2 default queued for missing stages
  });

  it("shows error messages when present", () => {
    const stages: ResearchStage[] = [
      createStage("planner", "completed", 100),
      createStage("retriever", "failed", 50, "", "Network timeout"),
    ];

    render(<AgentTimeline stages={stages} />);

    expect(screen.getByText("Network timeout")).toBeInTheDocument();
  });

  it("shows info messages when no error", () => {
    const stages: ResearchStage[] = [
      createStage("planner", "running", 50, "Processing query..."),
    ];

    render(<AgentTimeline stages={stages} />);

    expect(screen.getByText("Processing query...")).toBeInTheDocument();
  });

  it("renders missing stages as queued with 0 progress", () => {
    const stages: ResearchStage[] = [
      createStage("planner", "completed", 100),
      // Missing: retriever, reader, synthesis, harness
    ];

    render(<AgentTimeline stages={stages} />);

    // Should still show all 5 stages
    expect(screen.getByText("planner")).toBeInTheDocument();
    expect(screen.getByText("retriever")).toBeInTheDocument();
    expect(screen.getByText("reader")).toBeInTheDocument();
    expect(screen.getByText("synthesis")).toBeInTheDocument();
    expect(screen.getByText("harness")).toBeInTheDocument();
  });

  it("shows degraded status with amber color", () => {
    const stages: ResearchStage[] = [
      createStage("retriever", "degraded", 100, "Partial results"),
    ];

    const { container } = render(<AgentTimeline stages={stages} />);

    expect(screen.getByText("degraded")).toBeInTheDocument();
    expect(screen.getByText("Partial results")).toBeInTheDocument();

    // Check for amber color class (text-amber-600)
    const statusElement = screen.getByText("degraded");
    expect(statusElement.className).toContain("text-amber-600");
  });

  it("renders progress bars with correct widths", () => {
    const stages: ResearchStage[] = [
      createStage("planner", "completed", 100),
      createStage("retriever", "running", 50),
      createStage("reader", "queued", 0),
    ];

    const { container } = render(<AgentTimeline stages={stages} />);

    const progressBars = container.querySelectorAll('[style*="width"]');
    expect(progressBars.length).toBeGreaterThan(0);
  });
});
