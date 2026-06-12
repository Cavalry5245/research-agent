# MCP Agent Integration Design Spec

> **For agentic workers:** This spec describes transforming ResearchAgent into a complete MCP Agent system.

**Goal:** Transform ResearchAgent into a production-ready MCP Agent that calls external tools (Zotero, Semantic Scholar, arXiv) through the Model Context Protocol, with automatic MCP server lifecycle management and graceful degradation.

**Context:** This is a job-seeking project targeting the "LLM & Agent Application Development Intern" position. The implementation must demonstrate: Agent tool invocation, multi-tool integration, workflow orchestration, and system stability.

**Architecture:** Agent-as-Client pattern with managed MCP servers

```
ResearchAgent (MCP Agent Core)
│
├─ MCP Client Layer (New)
│   ├─ MCPClientManager: Lifecycle management for MCP servers
│   ├─ MCPToolProxy: Unified tool calling interface
│   └─ Health checks & auto-restart
│
├─ MCP Servers (Auto-managed)
│   ├─ Zotero MCP Server (zotero-mcp-server package)
│   ├─ Semantic Scholar MCP Server (TBD: find or build)
│   └─ arXiv MCP Server (TBD: find or build)
│
├─ Tool Layer (Refactored)
│   ├─ Primary: MCP tool calls
│   └─ Fallback: Direct database/API calls
│
├─ LLM Layer (Unchanged)
│   └─ OpenAI-compatible API with API key
│
└─ Local Tools (Unchanged)
    └─ Obsidian: Direct Markdown writes
```

**Tech Stack:**
- **MCP Client**: `mcp` >= 1.2.0, `httpx`
- **MCP Servers**: `zotero-mcp-server` (auto-installed as dependency)
- **Existing**: FastAPI, Pydantic, LangChain, Streamlit

---

## Phase 1: MCP Client Infrastructure

**Goal:** Build the foundation for MCP tool calling

### 1.1 MCP Client Manager

**Component:** `app/mcp/client_manager.py`

Manages the lifecycle of MCP server processes:

```python
class MCPServerConfig:
    name: str                    # e.g., "zotero"
    command: list[str]           # e.g., ["zotero-mcp"]
    env: dict[str, str]          # Environment variables
    stdio_transport: bool = True # Use stdio (default) or SSE
    auto_restart: bool = True
    health_check_interval: float = 30.0

class MCPClientManager:
    def start_server(config: MCPServerConfig) -> MCPClient
    def stop_server(name: str) -> None
    def restart_server(name: str) -> None
    def get_client(name: str) -> MCPClient | None
    def health_check_all() -> dict[str, bool]
    def shutdown_all() -> None
```

**Responsibilities:**
- Start MCP server subprocesses with correct environment
- Monitor health via periodic tool listing
- Auto-restart on crashes
- Graceful shutdown on app termination
- Thread-safe access to MCP clients

**Key Design Decision:** Use `subprocess.Popen` with stdio transport (not SSE) because:
- Zotero MCP server defaults to stdio
- Simpler than HTTP tunneling
- Suitable for local development

### 1.2 MCP Tool Proxy

**Component:** `app/mcp/tool_proxy.py`

Unified interface for calling MCP tools:

```python
class MCPToolCall:
    server_name: str
    tool_name: str
    arguments: dict[str, Any]

class MCPToolResult:
    success: bool
    result: Any | None
    error: str | None
    duration_ms: float
    server_name: str
    tool_name: str

class MCPToolProxy:
    def __init__(self, client_manager: MCPClientManager):
        ...
    
    def call_tool(self, call: MCPToolCall) -> MCPToolResult:
        # 1. Get client from manager
        # 2. Invoke tool via MCP protocol
        # 3. Handle errors with retries
        # 4. Return structured result
    
    def list_available_tools(self) -> dict[str, list[str]]:
        # Returns: {server_name: [tool_names]}
    
    async def call_tool_async(self, call: MCPToolCall) -> MCPToolResult:
        # Async version for concurrent calls
```

**Error Handling:**
- Connection errors → trigger restart and retry once
- Tool errors → return MCPToolResult with error field
- Timeout → configurable per-tool (default 30s)

### 1.3 Configuration

**Component:** `app/config.py` (extend existing)

```python
class Settings(BaseSettings):
    # ... existing fields ...
    
    # MCP Configuration
    mcp_enabled: bool = True
    mcp_startup_timeout: float = 10.0
    mcp_health_check_interval: float = 30.0
    mcp_tool_timeout: float = 30.0
    
    # Zotero MCP
    zotero_mcp_enabled: bool = True
    zotero_mcp_auto_install: bool = True
    
    # Semantic Scholar MCP
    semantic_scholar_mcp_enabled: bool = False
    
    # arXiv MCP  
    arxiv_mcp_enabled: bool = False
```

**Design Principle:** Feature flags for gradual rollout

---

## Phase 2: Zotero MCP Integration

**Goal:** Replace `ZoteroLocalHttpClient` with Zotero MCP Server

### 2.1 Zotero MCP Adapter

**Component:** `app/research_workflow/zotero_mcp_adapter.py`

Adapter that translates between ResearchAgent's interface and Zotero MCP tools:

```python
class ZoteroMCPAdapter:
    def __init__(self, tool_proxy: MCPToolProxy):
        self._proxy = tool_proxy
        self._server_name = "zotero"
    
    def list_collection_items(self, collection_id: str) -> list[ZoteroCollectionItem]:
        # Call: zotero.search_library with collection filter
        # Transform MCP result to ZoteroCollectionItem
        result = self._proxy.call_tool(MCPToolCall(
            server_name=self._server_name,
            tool_name="search_library",
            arguments={"collection": collection_id}
        ))
        
        if not result.success:
            raise ZoteroMCPError(result.error)
        
        return [self._parse_item(item) for item in result.result]
    
    def get_item_pdf(self, item_key: str) -> str | None:
        # Call: zotero.get_content for PDF path
        ...
```

**Mapping:**
- `list_collection_items()` → `zotero.search_library` + collection filter
- PDF resolution → `zotero.get_content` or fallback to local path parsing

### 2.2 Fallback Strategy

**Component:** `app/research_workflow/zotero_intake.py` (refactor)

Layered fallback:

```python
class ZoteroCollectionClient:
    """Abstract interface"""
    def list_collection_items(collection_id: str) -> list[ZoteroCollectionItem]

# Layer 1: MCP (Primary)
class ZoteroMCPClient(ZoteroCollectionClient):
    ...

# Layer 2: HTTP API (Deprecated but keep as fallback)
class ZoteroLocalHttpClient(ZoteroCollectionClient):
    ...

# Layer 3: Direct Database (Requires Zotero closed)
class ZoteroSQLiteClient(ZoteroCollectionClient):
    def __init__(self, db_path: Path, prompt_user: Callable[[str], bool]):
        self._db_path = db_path
        self._prompt_user = prompt_user
    
    def list_collection_items(self, collection_id: str):
        # Try to open database
        # If locked: prompt user to close Zotero
        # Wait and retry
        ...

# Factory
def create_zotero_client(settings: Settings, ui_prompter) -> ZoteroCollectionClient:
    if settings.zotero_mcp_enabled:
        try:
            return ZoteroMCPClient(...)
        except MCPServerStartError:
            logger.warning("Zotero MCP failed, falling back to HTTP")
    
    if settings.zotero_local:
        try:
            return ZoteroLocalHttpClient(...)
        except ConnectionError:
            logger.warning("Zotero HTTP failed, falling back to database")
    
    return ZoteroSQLiteClient(
        db_path=Path(settings.zotero_data_dir) / "zotero.sqlite",
        prompt_user=ui_prompter
    )
```

**User Experience:**
- MCP fails → Automatic fallback to HTTP (silent)
- HTTP fails → Automatic fallback to DB
- DB locked → Show modal: "Please close Zotero to continue" with retry/cancel buttons

### 2.3 Auto-Installation

**Component:** `app/mcp/installer.py`

```python
def ensure_zotero_mcp_installed() -> bool:
    """Check if zotero-mcp-server is installed, install if missing"""
    try:
        result = subprocess.run(
            ["zotero-mcp", "--version"],
            capture_output=True,
            timeout=5
        )
        return result.returncode == 0
    except FileNotFoundError:
        logger.info("zotero-mcp-server not found, installing...")
        subprocess.run(
            ["pip", "install", "zotero-mcp-server"],
            check=True
        )
        return True
```

Called on first startup if `zotero_mcp_auto_install=True`

---

## Phase 3: Semantic Scholar & arXiv MCP

**Goal:** Extend MCP architecture to other external services

### 3.1 Discovery Phase

**Task:** Find existing MCP servers or build minimal ones

**Semantic Scholar:**
- Check if `semantic-scholar-mcp-server` exists on PyPI
- If not: Build minimal MCP server wrapping Semantic Scholar API
  - Tools: `search_papers`, `get_paper_details`, `get_citations`
  - Location: `third_party/semantic_scholar_mcp/`

**arXiv:**
- Check if `arxiv-mcp-server` exists
- If not: Build minimal wrapper for arXiv API
  - Tools: `search_arxiv`, `get_paper_metadata`, `download_pdf`
  - Location: `third_party/arxiv_mcp/`

**Design Decision:** If no existing servers found, Phase 3 builds minimal MCP servers (50-100 LOC each) that wrap API calls. These are proof-of-concept quality, suitable for demo.

### 3.2 Adapter Pattern

Replicate Zotero adapter pattern:

```python
# app/research_workflow/semantic_scholar_mcp_adapter.py
class SemanticScholarMCPAdapter:
    def search_papers(self, query: str, limit: int) -> list[dict]:
        ...
    
    def get_paper_details(self, paper_id: str) -> dict:
        ...

# app/research_workflow/arxiv_mcp_adapter.py  
class ArxivMCPAdapter:
    def search_papers(self, query: str, max_results: int) -> list[dict]:
        ...
```

**Integration Point:** `tool_adapters.py` uses these adapters instead of direct API calls

---

## Phase 4: Integration & Testing

### 4.1 Service Layer Integration

**Component:** `app/research_workflow/service.py` (minimal changes)

```python
class ResearchRunService:
    def __init__(
        self,
        store: FileResearchRunStore,
        vault_root: str | Path,
        mcp_manager: MCPClientManager | None = None,  # New
        tool_registry_factory: Callable[[], ToolRegistry] | None = None,
    ):
        self._mcp_manager = mcp_manager or self._create_default_mcp_manager()
        ...
    
    def _create_default_mcp_manager(self) -> MCPClientManager:
        manager = MCPClientManager()
        if settings.zotero_mcp_enabled:
            manager.start_server(MCPServerConfig(
                name="zotero",
                command=["zotero-mcp"],
                env={"ZOTERO_DATA_DIR": settings.zotero_data_dir}
            ))
        # ... start other MCP servers
        return manager
```

**Key:** ResearchRunService now owns MCPClientManager lifecycle

### 4.2 UI Integration

**Component:** `ui/streamlit_app.py`

Show MCP server status:

```python
with st.sidebar:
    st.header("🔌 MCP Tools")
    
    mcp_status = get_mcp_status()
    for server_name, status in mcp_status.items():
        icon = "🟢" if status["running"] else "🔴"
        st.caption(f"{icon} {server_name}: {status['tool_count']} tools")
        
        if not status["running"]:
            if st.button(f"Restart {server_name}"):
                restart_mcp_server(server_name)
```

**User Prompt for DB Fallback:**

```python
def prompt_close_zotero() -> bool:
    """Show modal asking user to close Zotero"""
    return st.dialog(
        "Zotero is locked",
        "Please close Zotero to access the database directly. Retry after closing?",
        buttons=["Retry", "Cancel"]
    ) == "Retry"
```

### 4.3 Testing Strategy

**Unit Tests:**
- `tests/mcp/test_client_manager.py`: Server lifecycle
- `tests/mcp/test_tool_proxy.py`: Tool calling
- `tests/research_workflow/test_zotero_mcp_adapter.py`: Zotero integration

**Integration Tests:**
- `tests/integration/test_mcp_e2e.py`: Full flow with real MCP servers
- Mock MCP servers for CI/CD

**Manual QA:**
1. Start ResearchAgent with Zotero closed → Verify auto-start of Zotero MCP
2. Kill Zotero MCP mid-run → Verify auto-restart
3. Zotero database locked → Verify user prompt
4. All MCP servers disabled → Verify fallback to legacy HTTP/API

---

## Phase 5: Documentation & Demo

### 5.1 Architecture Diagram

Create visual diagram showing:
- ResearchAgent as MCP Agent
- Multiple MCP servers
- Fallback layers
- Tool call flow

**Tool:** Mermaid diagram in `docs/ARCHITECTURE.md`

### 5.2 Demo Script

**Scenario:** "Multi-Source Literature Review"

1. Start ResearchAgent
2. Show MCP server status (3 servers running)
3. Create Research Run from Zotero collection
4. Show logs: Zotero MCP calls for collection items
5. Query Semantic Scholar MCP for citation counts
6. Search arXiv MCP for related preprints
7. Generate Knowledge Pack with citations from all 3 sources

**Deliverable:** 5-minute video demo + README with screenshots

### 5.3 JD Alignment Document

**File:** `docs/JD_CAPABILITIES.md`

Map each JD requirement to implemented features:

| JD Requirement | Implementation | Code Location |
|---|---|---|
| Agent system design | MCP Agent architecture | `app/mcp/` |
| Tool calling | MCPToolProxy | `app/mcp/tool_proxy.py` |
| Multi-tool integration | Zotero + Semantic Scholar + arXiv | `app/research_workflow/*_adapter.py` |
| Workflow orchestration | ResearchRunService | `app/research_workflow/service.py` |
| Error handling & stability | Fallback strategy | `app/research_workflow/zotero_intake.py` |

---

## Non-Goals (Out of Scope)

1. **Multi-Agent Collaboration:** Single agent with multiple tools, not multiple agents
2. **LLM Tool Selection:** Tools are called programmatically, not by LLM function calling
3. **Production Deployment:** Demo quality, not production-hardened
4. **Custom MCP Protocol:** Use standard MCP, no extensions

---

## Success Criteria

**Technical:**
- [ ] 3 MCP servers integrated (Zotero, Semantic Scholar, arXiv)
- [ ] <10s startup time for all MCP servers
- [ ] <5% error rate in MCP tool calls
- [ ] Graceful degradation to fallbacks
- [ ] 100% test coverage for MCP layer

**JD Alignment:**
- [ ] Demonstrates Agent tool calling (MCP)
- [ ] Shows multi-tool integration
- [ ] Exhibits workflow orchestration
- [ ] Proves system stability (fallbacks, auto-restart)
- [ ] Includes documentation & demo video

**User Experience:**
- [ ] Zero manual MCP server management required
- [ ] Clear status indicators in UI
- [ ] Helpful error messages (not stack traces)
- [ ] <30s end-to-end for typical research run

---

## Implementation Order

1. **Week 1:** Phase 1 (MCP Client Infrastructure) - Foundation
2. **Week 2:** Phase 2 (Zotero MCP) - First integration
3. **Week 3:** Phase 3 (Semantic Scholar & arXiv) - Expand
4. **Week 4:** Phase 4 (Integration & Testing) + Phase 5 (Docs & Demo) - Polish

**Rationale:** Build foundation first, prove with one tool (Zotero), then replicate pattern for others.

---

## Risk Mitigation

**Risk 1:** Zotero MCP server crashes frequently
- **Mitigation:** Auto-restart + fallback to HTTP API

**Risk 2:** No existing Semantic Scholar/arXiv MCP servers
- **Mitigation:** Build minimal wrappers (50-100 LOC each)

**Risk 3:** MCP adds too much latency
- **Mitigation:** Measure in Phase 2; if >2s overhead, optimize or simplify

**Risk 4:** User confusion with MCP vs HTTP vs DB layers
- **Mitigation:** Hide complexity; only surface "Retry" button when needed

---

## Open Questions

1. **Q:** Should MCPClientManager run MCP servers as threads or subprocesses?
   **A:** Subprocesses. Isolation, easier to kill, standard MCP pattern.

2. **Q:** stdio or SSE transport for MCP?
   **A:** stdio. Simpler, default for zotero-mcp-server.

3. **Q:** Should we cache MCP tool schemas?
   **A:** Yes, cache on startup. Reduces calls and latency.

4. **Q:** What if zotero-mcp-server requires Zotero to be running?
   **A:** Test and document. If required, add to user guide.

---

**Next Step:** Create implementation plan with bite-sized tasks.
