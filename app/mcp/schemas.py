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


class Paper(BaseModel):
    """Unified paper shape normalized across all academic search sources.

    Every MCP search source (the external paper-search-mcp server and the
    project's own minimal arXiv / Semantic Scholar servers) is mapped to this
    model by ``app.mcp.paper_normalizer.normalize_paper`` so downstream
    workflow code never sees source-specific dict layouts.
    """

    paper_id: str = ""
    title: str = ""
    authors: list[str] = Field(default_factory=list)
    abstract: str = ""
    doi: str = ""
    pdf_url: str = ""
    url: str = ""
    source: str = ""
    published_date: str | None = None
    year: int | None = None
    citation_count: int = 0
    extra: dict[str, Any] = Field(default_factory=dict)
