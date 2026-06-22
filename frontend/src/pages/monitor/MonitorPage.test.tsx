import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { MonitorPage } from "./MonitorPage";
import * as monitorApi from "../../api/monitor";

vi.mock("../../api/monitor", () => ({
  getTraceStats: vi.fn(),
  getTraces: vi.fn()
}));

function renderPage() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={client}><MonitorPage /></QueryClientProvider>);
}

beforeEach(() => {
  vi.clearAllMocks();
  vi.mocked(monitorApi.getTraceStats).mockResolvedValue({
    total_traces: 1,
    by_agent: { planner: 1 },
    by_action: { route: 1 },
    avg_duration_ms: 12.5
  });
  vi.mocked(monitorApi.getTraces).mockResolvedValue({
    count: 1,
    traces: [{
      id: "trace_001",
      conversation_id: "conv_001",
      agent_id: "planner",
      action: "route",
      input_data: { task: "x" },
      output_data: { ok: true },
      duration_ms: 12.5,
      created_at: 1760000000,
      metadata: {}
    }]
  });
});

describe("MonitorPage", () => {
  it("renders stats and applies filters", async () => {
    const user = userEvent.setup();
    renderPage();

    await waitFor(() => expect(screen.getByText("trace_001")).toBeInTheDocument());
    expect(screen.getAllByText("12.5 ms").length).toBeGreaterThan(0);

    await user.type(screen.getByLabelText(/conversation id/i), "conv_001");
    await user.type(screen.getByLabelText(/agent id/i), "planner");
    await user.click(screen.getByRole("button", { name: "Apply" }));

    expect(monitorApi.getTraces).toHaveBeenLastCalledWith({ conversationId: "conv_001", agentId: "planner", limit: 100 });
  });
});
