import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { AgentPage } from "./AgentPage";
import * as agentApi from "../../api/agent";

vi.mock("../../api/agent", () => ({ executeAgent: vi.fn() }));

function renderPage() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={client}><AgentPage /></QueryClientProvider>);
}

beforeEach(() => {
  vi.clearAllMocks();
  vi.mocked(agentApi.executeAgent).mockResolvedValue({
    task: "Summarize papers",
    answer: "The papers focus on retrieval.",
    conversation_id: "conv_001",
    task_type: "summary"
  });
});

describe("AgentPage", () => {
  it("executes an agent task", async () => {
    const user = userEvent.setup();
    renderPage();

    await user.click(screen.getByRole("button", { name: /summarize methods/i }));
    expect(screen.getByDisplayValue("Summarize the key methods in the local library.")).toBeInTheDocument();

    await user.clear(screen.getByPlaceholderText(/describe the research task/i));
    await user.type(screen.getByPlaceholderText(/describe the research task/i), "Summarize papers");
    await user.selectOptions(screen.getByLabelText(/mode/i), "supervisor");
    await user.type(screen.getByLabelText(/continue conversation/i), "conv_001");
    await user.click(screen.getByRole("button", { name: /run agent/i }));

    await waitFor(() => expect(screen.getByText("The papers focus on retrieval.")).toBeInTheDocument());
    expect(screen.getByText("Answer")).toBeInTheDocument();
    expect(screen.getByText("Conversation: conv_001")).toBeInTheDocument();
    expect(vi.mocked(agentApi.executeAgent).mock.calls[0][0]).toEqual({
      task: "Summarize papers",
      mode: "supervisor",
      conversation_id: "conv_001"
    });
  });

  it("shows running feedback while the agent is executing", async () => {
    const user = userEvent.setup();
    vi.mocked(agentApi.executeAgent).mockImplementation(() => new Promise(() => undefined));
    renderPage();

    await user.click(screen.getByRole("button", { name: /find research gaps/i }));
    await user.click(screen.getByRole("button", { name: /run agent/i }));

    expect(screen.getByText("Agent is working")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /agent working/i })).toBeDisabled();
  });
});
