from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class ToolParameter:
    name: str
    type: str
    description: str
    required: bool = True


@dataclass
class ToolResult:
    success: bool
    data: dict | None = None
    error: str | None = None


class BaseTool(ABC):
    name: str = ""
    description: str = ""

    @property
    @abstractmethod
    def parameters(self) -> list[ToolParameter]:
        ...

    @abstractmethod
    def execute(self, **kwargs) -> ToolResult:
        ...

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "description": self.description,
            "parameters": [
                {
                    "name": p.name,
                    "type": p.type,
                    "description": p.description,
                    "required": p.required,
                }
                for p in self.parameters
            ],
        }
