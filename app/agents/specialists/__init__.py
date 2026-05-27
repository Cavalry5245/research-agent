"""Base interface for specialist agents in the supervisor architecture."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class AgentResult:
    """Standard result returned by any specialist agent."""

    success: bool
    output: str
    data: dict[str, Any] = field(default_factory=dict)
    agent_id: str = ""
    error: str | None = None


class BaseSpecialist(ABC):
    """Abstract base for specialist agents.

    Each specialist has a role, goal, and set of capabilities.
    The supervisor routes tasks to the appropriate specialist based on intent.
    """

    name: str = ""
    role: str = ""
    goal: str = ""
    capabilities: list[str] = []

    @abstractmethod
    def execute(self, task: str, context: dict[str, Any] | None = None) -> AgentResult:
        """Execute a task within this specialist's domain."""
        ...

    def can_handle(self, task_type: str) -> bool:
        return task_type in self.capabilities

    def describe(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "role": self.role,
            "goal": self.goal,
            "capabilities": self.capabilities,
        }
