import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { HarnessSummary } from "./HarnessSummary";

describe("HarnessSummary", () => {
  it("displays all verification status counts", () => {
    const summary = {
      supported: 10,
      weak: 3,
      unverified: 0,
      numeric_trace_missing: 2,
      conflict_detected: 1,
    };

    render(<HarnessSummary summary={summary} />);

    expect(screen.getByText("10")).toBeInTheDocument(); // supported
    expect(screen.getByText("3")).toBeInTheDocument(); // weak
    expect(screen.getByText("2")).toBeInTheDocument(); // numeric_trace_missing
    expect(screen.getByText("1")).toBeInTheDocument(); // conflict_detected
  });

  it("shows zero counts correctly", () => {
    const summary = {
      supported: 5,
      weak: 0,
      unverified: 0,
      numeric_trace_missing: 0,
      conflict_detected: 0,
    };

    render(<HarnessSummary summary={summary} />);

    expect(screen.getByText("5")).toBeInTheDocument();
    // All other counts should be 0
    const zeros = screen.getAllByText("0");
    expect(zeros.length).toBeGreaterThanOrEqual(3);
  });

  it("renders nothing when summary is empty", () => {
    const summary = {};

    const { container } = render(<HarnessSummary summary={summary} />);

    expect(container.firstChild).toBeNull();
  });

  it("displays labels for each verification status", () => {
    const summary = {
      supported: 1,
      weak: 1,
      unverified: 1,
      numeric_trace_missing: 1,
      conflict_detected: 1,
    };

    render(<HarnessSummary summary={summary} />);

    expect(screen.getByText(/supported/i)).toBeInTheDocument();
    expect(screen.getByText(/weak/i)).toBeInTheDocument();
    expect(screen.getByText(/unverified/i)).toBeInTheDocument();
    expect(screen.getByText(/numeric.*missing/i)).toBeInTheDocument();
    expect(screen.getByText(/conflict/i)).toBeInTheDocument();
  });

  it("highlights problematic statuses", () => {
    const summary = {
      supported: 10,
      weak: 2,
      unverified: 1,
      numeric_trace_missing: 3,
      conflict_detected: 4,
    };

    const { container } = render(<HarnessSummary summary={summary} />);

    // Check that conflict_detected has red styling
    const conflictElement = screen.getByText("4").closest("div");
    expect(conflictElement?.className).toContain("red");
  });

  it("calculates total claims correctly", () => {
    const summary = {
      supported: 10,
      weak: 3,
      unverified: 2,
      numeric_trace_missing: 1,
      conflict_detected: 4,
    };

    render(<HarnessSummary summary={summary} />);

    // Total should be 20
    expect(screen.getByText(/20/)).toBeInTheDocument();
  });
});
