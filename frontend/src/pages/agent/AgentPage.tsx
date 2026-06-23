import { FormEvent, useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { executeAgent } from "../../api/agent";
import { EmptyState } from "../../components/empty-state/EmptyState";
import { ErrorState } from "../../components/error-state/ErrorState";
import { MarkdownContent } from "../../components/common/MarkdownContent";

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
          Execute paper research tasks through the backend agent.
        </p>
      </section>

      <form onSubmit={handleSubmit} className="rounded-md border border-line bg-panel p-4 shadow-panel">
        <div className="grid gap-4 xl:grid-cols-[1fr_16rem]">
          <label className="block">
            <span className="text-xs font-medium uppercase text-muted">Task</span>
            <textarea
              value={task}
              onChange={(event) => setTask(event.target.value)}
              rows={6}
              placeholder="Summarize the key methods in the local library."
              className="mt-1 w-full resize-y rounded-md border border-line px-3 py-2 text-sm text-ink"
            />
          </label>
          <div className="space-y-3">
            <label className="block">
              <span className="text-xs font-medium uppercase text-muted">Mode</span>
              <select value={mode} onChange={(event) => setMode(event.target.value as "react" | "supervisor")} className="mt-1 w-full rounded-md border border-line px-3 py-2 text-sm">
                <option value="react">ReAct</option>
                <option value="supervisor">Supervisor</option>
              </select>
            </label>
            <label className="block">
              <span className="text-xs font-medium uppercase text-muted">Conversation ID</span>
              <input value={conversationId} onChange={(event) => setConversationId(event.target.value)} className="mt-1 w-full rounded-md border border-line px-3 py-2 text-sm" />
            </label>
            <button type="submit" disabled={!task.trim() || mutation.isPending} className="w-full rounded-md bg-accent px-4 py-2 text-sm font-medium text-white hover:bg-accent-hover disabled:opacity-60">
              {mutation.isPending ? "Running" : "Run agent"}
            </button>
          </div>
        </div>
      </form>

      {mutation.error && <ErrorState title="Agent execution failed" message={(mutation.error as Error).message} />}
      {mutation.data ? (
        <section className="rounded-md border border-line bg-panel p-4 shadow-panel">
          <div className="flex flex-wrap items-center gap-3 text-xs text-muted">
            <span>Task: {mutation.data.task}</span>
            {mutation.data.conversation_id && <span>Conversation: {mutation.data.conversation_id}</span>}
            {mutation.data.task_type && <span>Type: {mutation.data.task_type}</span>}
          </div>
          <MarkdownContent content={mutation.data.answer} className="mt-4 rounded-md bg-surface p-4" />
        </section>
      ) : (
        <EmptyState title="No agent result yet" description="Run an agent task to see the response here." />
      )}
    </div>
  );
}
