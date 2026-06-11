from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator


class MCPServerConfig(BaseModel):
    name: str = Field(pattern=r'^[a-zA-Z0-9_-]+$', min_length=1)
    command: list[str] = Field(min_length=1)
    env: dict[str, str] = Field(default_factory=dict)
    cwd: str | None = None
    # Reserved for future implementation
    auto_restart: bool = True
    health_check_interval: float = 30.0
    startup_timeout: float = 10.0


class MCPToolCall(BaseModel):
    server_name: str
    tool_name: str
    arguments: dict[str, Any] = Field(default_factory=dict)


MCPToolStatus = Literal["success", "error", "timeout"]


class MCPToolResult(BaseModel):
    status: MCPToolStatus
    result: Any = None
    error: str | None = None
    duration_ms: float = Field(ge=0.0)
    server_name: str
    tool_name: str

    @model_validator(mode='after')
    def validate_error_status(self):
        if self.status == 'error' and self.error is None:
            raise ValueError('error field is required when status is "error"')
        return self
