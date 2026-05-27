"""Shared state definitions for the supervisor multi-agent graph."""

from __future__ import annotations

from typing import Any, Literal, TypedDict

TaskType = Literal[
    "upload",
    "parse",
    "extract",
    "note",
    "export",
    "qa",
    "question",
    "search",
    "compare",
    "unknown",
]

TASK_TYPE_TO_SPECIALIST: dict[TaskType, str] = {
    "upload": "extractor",
    "parse": "extractor",
    "extract": "extractor",
    "note": "summarizer",
    "export": "summarizer",
    "qa": "qa",
    "question": "qa",
    "search": "qa",
    "compare": "comparator",
}


class Delegation(TypedDict):
    agent: str
    task: str
    context: dict[str, Any]


class SupervisorState(TypedDict, total=False):
    user_input: str
    task_type: TaskType
    delegations: list[Delegation]
    results: list[dict[str, Any]]
    final_answer: str
    error: str | None
    context: dict[str, Any]
