import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { StatusBadge } from "./StatusBadge";

describe("StatusBadge", () => {
  it("renders fallback active state with accessible text", () => {
    render(<StatusBadge status="fallback_active" />);
    expect(screen.getByText("fallback active")).toBeInTheDocument();
  });

  it("renders failed state with alert tone", () => {
    render(<StatusBadge status="failed" label="failed" />);
    expect(screen.getByText("failed")).toHaveClass("bg-red-50");
  });
});
