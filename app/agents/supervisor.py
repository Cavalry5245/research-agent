"""Supervisor Agent — routes user requests to specialist agents via LangGraph StateGraph."""

from __future__ import annotations

import logging
import time
from typing import Any

from langgraph.graph import END, StateGraph

from app.agents.specialists import AgentResult, BaseSpecialist
from app.agents.specialists.comparator_agent import ComparatorAgent
from app.agents.specialists.extractor_agent import ExtractorAgent
from app.agents.specialists.qa_agent import QAAgent
from app.agents.specialists.summarizer_agent import SummarizerAgent
from app.agents.state import TASK_TYPE_TO_SPECIALIST, Delegation, SupervisorState, TaskType

logger = logging.getLogger(__name__)

INTENT_KEYWORDS: dict[TaskType, list[str]] = {
    "upload": ["上传", "upload", "添加论文", "add paper"],
    "parse": ["解析", "parse", "提取", "extract"],
    "extract": ["信息", "info", "结构", "structure"],
    "note": ["笔记", "note", "总结", "summarize", "摘要", "summary"],
    "export": ["导出", "export", "下载", "download", "markdown"],
    "qa": ["问", "ask", "什么", "what", "how", "why", "回答", "answer", "？", "?"],
    "question": ["问题", "question"],
    "search": ["搜索", "search", "查找", "find", "检索", "retrieve"],
    "compare": ["对比", "compare", "比较", "contrast", "差异", "diff"],
}


def classify_intent(user_input: str) -> TaskType:
    text = user_input.lower()
    scores: dict[TaskType, int] = {}
    for task_type, keywords in INTENT_KEYWORDS.items():
        score = sum(1 for kw in keywords if kw in text)
        if score > 0:
            scores[task_type] = score
    if not scores:
        return "qa"
    return max(scores, key=scores.get)


# ── Graph Nodes ──────────────────────────────────────────────────────────────


def route_node(state: SupervisorState) -> dict:
    user_input = state["user_input"]
    task_type = classify_intent(user_input)
    specialist_name = TASK_TYPE_TO_SPECIALIST.get(task_type, "qa")
    delegation = Delegation(agent=specialist_name, task=user_input, context=state.get("context", {}))
    return {"task_type": task_type, "delegations": [delegation]}


def execute_node(state: SupervisorState) -> dict:
    delegations = state.get("delegations", [])
    results: list[dict[str, Any]] = []

    specialists: dict[str, BaseSpecialist] = {
        "extractor": ExtractorAgent(),
        "summarizer": SummarizerAgent(),
        "qa": QAAgent(enable_rerank=True, enable_query_rewrite=False),
        "comparator": ComparatorAgent(),
    }

    for delegation in delegations:
        agent_name = delegation["agent"]
        specialist = specialists.get(agent_name)
        if not specialist:
            results.append({"success": False, "error": f"Unknown agent: {agent_name}", "agent_id": agent_name})
            continue

        started = time.perf_counter()
        result = specialist.execute(delegation["task"], context=delegation.get("context"))
        duration_ms = (time.perf_counter() - started) * 1000

        results.append({
            "success": result.success,
            "output": result.output,
            "data": result.data,
            "agent_id": result.agent_id,
            "error": result.error,
            "duration_ms": round(duration_ms, 2),
        })

    return {"results": results}


def synthesize_node(state: SupervisorState) -> dict:
    results = state.get("results", [])
    if not results:
        return {"final_answer": "无法处理该请求。", "error": "No results from specialists"}

    successful = [r for r in results if r.get("success")]
    if successful:
        outputs = [r["output"] for r in successful if r.get("output")]
        final_answer = "\n\n".join(outputs) if outputs else "任务已完成。"
        return {"final_answer": final_answer, "error": None}
    else:
        errors = [r.get("error", "unknown error") for r in results]
        return {"final_answer": "", "error": "; ".join(errors)}


# ── Graph Construction ───────────────────────────────────────────────────────


def build_supervisor_graph() -> StateGraph:
    graph = StateGraph(SupervisorState)
    graph.add_node("route", route_node)
    graph.add_node("execute", execute_node)
    graph.add_node("synthesize", synthesize_node)

    graph.set_entry_point("route")
    graph.add_edge("route", "execute")
    graph.add_edge("execute", "synthesize")
    graph.add_edge("synthesize", END)

    return graph


class SupervisorAgent:
    """High-level supervisor that routes tasks to specialist agents."""

    def __init__(self):
        graph_builder = build_supervisor_graph()
        self._graph = graph_builder.compile()
        self._specialists = {
            "extractor": ExtractorAgent(),
            "summarizer": SummarizerAgent(),
            "qa": QAAgent(),
            "comparator": ComparatorAgent(),
        }

    @property
    def specialists(self) -> dict[str, BaseSpecialist]:
        return self._specialists

    def run(self, user_input: str, context: dict[str, Any] | None = None) -> dict[str, Any]:
        initial_state: SupervisorState = {
            "user_input": user_input,
            "task_type": "unknown",
            "delegations": [],
            "results": [],
            "final_answer": "",
            "error": None,
            "context": context or {},
        }

        final_state = self._graph.invoke(initial_state)
        return {
            "answer": final_state.get("final_answer", ""),
            "task_type": final_state.get("task_type", "unknown"),
            "results": final_state.get("results", []),
            "error": final_state.get("error"),
        }

    def run_traced(
        self,
        user_input: str,
        context: dict[str, Any] | None = None,
        conversation_id: str | None = None,
        memory_store: Any | None = None,
    ) -> dict[str, Any]:
        """Execute with full observability — records routing decisions and delegation results."""
        from app.agents.decision_logger import DecisionLogger
        from app.agents.tracing import AgentTracer

        store = memory_store
        tracer = AgentTracer(store, conversation_id=conversation_id) if store else None
        decision_logger = DecisionLogger(store, conversation_id=conversation_id) if store else None

        # Route
        task_type = classify_intent(user_input)
        specialist_name = TASK_TYPE_TO_SPECIALIST.get(task_type, "qa")

        scores: dict[str, int] = {}
        text = user_input.lower()
        for tt, keywords in INTENT_KEYWORDS.items():
            score = sum(1 for kw in keywords if kw in text)
            if score > 0:
                scores[tt] = score

        if decision_logger:
            decision_logger.log_routing(
                user_input=user_input,
                classified_type=task_type,
                routed_to=specialist_name,
                confidence_scores=scores,
                rationale=f"keyword match → {task_type} (score {scores.get(task_type, 0)})",
            )

        # Execute
        specialists: dict[str, BaseSpecialist] = {
            "extractor": ExtractorAgent(),
            "summarizer": SummarizerAgent(),
            "qa": QAAgent(enable_rerank=True, enable_query_rewrite=False),
            "comparator": ComparatorAgent(),
        }

        specialist = specialists.get(specialist_name)
        if not specialist:
            return {"answer": "", "task_type": task_type, "results": [], "error": f"Unknown agent: {specialist_name}"}

        if tracer:
            with tracer.span(specialist_name, "delegation", input_data={"task": user_input[:200], "context": context or {}}) as span:
                started = time.perf_counter()
                result = specialist.execute(user_input, context=context)
                duration_ms = (time.perf_counter() - started) * 1000
                span.output_data = {"success": result.success, "output_preview": result.output[:200] if result.output else "", "error": result.error}
        else:
            started = time.perf_counter()
            result = specialist.execute(user_input, context=context)
            duration_ms = (time.perf_counter() - started) * 1000

        if decision_logger:
            decision_logger.log_delegation_result(
                agent_id=specialist_name,
                success=result.success,
                duration_ms=round(duration_ms, 2),
                output_summary=result.output[:200] if result.output else "",
                error=result.error,
            )

        answer = result.output if result.success else ""
        error = result.error if not result.success else None

        return {
            "answer": answer,
            "task_type": task_type,
            "results": [{"success": result.success, "output": result.output, "agent_id": specialist_name, "error": result.error, "duration_ms": round(duration_ms, 2)}],
            "error": error,
        }
