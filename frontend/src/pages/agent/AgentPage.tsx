import { FormEvent, useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { Bot, CheckCircle2, Clock, Sparkles } from "lucide-react";
import { executeAgent } from "../../api/agent";
import { EmptyState } from "../../components/empty-state/EmptyState";
import { ErrorState } from "../../components/error-state/ErrorState";
import { MarkdownContent } from "../../components/common/MarkdownContent";

const taskTemplates = [
  {
    label: "Summarize methods",
    value: "Summarize the key methods in the local library."
  },
  {
    label: "Find research gaps",
    value: "Find research gaps across the local paper library."
  },
  {
    label: "Propose experiments",
    value: "Propose experiment ideas based on the indexed papers."
  },
  {
    label: "Compare contributions",
    value: "Compare the main contributions of selected papers."
  }
];

export function AgentPage() {
  const [task, setTask] = useState("");
  const [mode, setMode] = useState<"react" | "supervisor">("react");
  const [conversationId, setConversationId] = useState("");

  const mutation = useMutation({
    mutationFn: executeAgent
  });

  const handleSubmit = (event: FormEvent) => {
    event.preventDefault();
    if (!task.trim()) return;
    mutation.mutate({
      task: task.trim(),
      mode,
      conversation_id: conversationId.trim() || null
    });
  };

  return (
    <div className="space-y-6">
      <section>
        <h1 className="text-2xl font-semibold text-ink">Agent</h1>
        <p className="mt-2 max-w-3xl text-sm leading-6 text-muted">
          Delegate open-ended research work to the backend agent.
        </p>
      </section>

      <form onSubmit={handleSubmit} className="rounded-md border border-line bg-panel p-4 shadow-panel">
        <div className="grid gap-5 xl:grid-cols-[1fr_18rem]">
          <div className="space-y-4">
            <div>
              <div className="flex items-center gap-2 text-xs font-medium uppercase text-muted">
                <Sparkles className="h-4 w-4" aria-hidden="true" />
                Task templates
              </div>
              <div className="mt-2 flex flex-wrap gap-2">
                {taskTemplates.map((template) => (
                  <button
                    key={template.label}
                    type="button"
                    onClick={() => setTask(template.value)}
                    className="rounded-md border border-line bg-white px-3 py-2 text-sm font-medium text-muted hover:bg-surface"
                  >
                    {template.label}
                  </button>
                ))}
              </div>
            </div>

            <label className="block">
              <span className="text-xs font-medium uppercase text-muted">Task</span>
              <textarea
                value={task}
                onChange={(event) => setTask(event.target.value)}
                rows={7}
                placeholder="Describe the research task you want the agent to complete."
                className="mt-1 w-full resize-y rounded-md border border-line px-3 py-2 text-sm text-ink"
              />
            </label>
          </div>

          <div className="rounded-md border border-line bg-surface p-4">
            <h2 className="flex items-center gap-2 text-sm font-semibold text-ink">
              <Bot className="h-4 w-4" aria-hidden="true" />
              Run settings
            </h2>
            <div className="mt-4 space-y-3">
              <label className="block">
                <span className="text-xs font-medium uppercase text-muted">Mode</span>
                <select value={mode} onChange={(event) => setMode(event.target.value as "react" | "supervisor")} className="mt-1 w-full rounded-md border border-line bg-white px-3 py-2 text-sm">
                  <option value="react">ReAct - tool-using reasoning</option>
                  <option value="supervisor">Supervisor - specialist routing</option>
                </select>
              </label>
              <label className="block">
                <span className="text-xs font-medium uppercase text-muted">Continue conversation</span>
                <input
                  value={conversationId}
                  onChange={(event) => setConversationId(event.target.value)}
                  placeholder="Optional conversation ID"
                  className="mt-1 w-full rounded-md border border-line bg-white px-3 py-2 text-sm"
                />
              </label>
              <button type="submit" disabled={!task.trim() || mutation.isPending} className="w-full rounded-md bg-accent px-4 py-2 text-sm font-medium text-white hover:bg-accent-hover disabled:opacity-60">
                {mutation.isPending ? "Agent working..." : "Run agent"}
              </button>
            </div>
          </div>
        </div>
      </form>

      {mutation.error && <ErrorState title="Agent execution failed" message={(mutation.error as Error).message} />}
      {mutation.isPending ? (
        <section className="rounded-md border border-line bg-panel p-5 shadow-panel">
          <div className="flex items-center gap-3">
            <span className="inline-flex h-10 w-10 items-center justify-center rounded-full bg-accent/10 text-accent">
              <Clock className="h-5 w-5" aria-hidden="true" />
            </span>
            <div>
              <h2 className="text-sm font-semibold text-ink">Agent is working</h2>
              <p className="mt-1 text-sm text-muted">Planning, calling tools, and preparing the answer.</p>
            </div>
          </div>
        </section>
      ) : mutation.data ? (
        <section className="rounded-md border border-line bg-panel p-4 shadow-panel">
          <div className="flex items-start justify-between gap-4">
            <div>
              <h2 className="flex items-center gap-2 text-base font-semibold text-ink">
                <CheckCircle2 className="h-5 w-5 text-emerald-600" aria-hidden="true" />
                Answer
              </h2>
              <div className="mt-2 flex flex-wrap items-center gap-2 text-xs text-muted">
                <span className="rounded-full bg-surface px-2 py-1">Mode: {mode}</span>
                {mutation.data.conversation_id && <span className="rounded-full bg-surface px-2 py-1">Conversation: {mutation.data.conversation_id}</span>}
                {mutation.data.task_type && <span className="rounded-full bg-surface px-2 py-1">Type: {mutation.data.task_type}</span>}
              </div>
            </div>
          </div>
          <p className="mt-4 rounded-md border border-line bg-surface px-3 py-2 text-sm text-muted">Task: {mutation.data.task}</p>
          <MarkdownContent content={mutation.data.answer} className="mt-4 rounded-md bg-surface p-4" />
        </section>
      ) : (
        <EmptyState title="Choose a task template or write your own" description="The agent can summarize, compare, plan, and inspect your paper library." />
      )}
    </div>
  );
}
