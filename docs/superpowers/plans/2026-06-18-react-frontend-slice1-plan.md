# React Frontend Slice 1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the first React replacement slice: FastAPI system status endpoint plus a Vite/React/TypeScript workspace shell and real-data dashboard.

**Architecture:** Keep Python services and Streamlit intact. Add one narrow FastAPI endpoint for aggregated runtime status, then create `frontend/` as a separate Vite app that calls the existing API and renders a dense developer-console/paper-knowledge workspace shell. This slice produces a usable dashboard and the foundation for later Papers, Workflow, QA, Compare, Agent, and Monitor slices.

**Tech Stack:** FastAPI, Pydantic, pytest, Vite, React, TypeScript, React Router, TanStack Query, Zustand, Tailwind CSS, Lucide React, Vitest, Testing Library.

---

## Scope Check

The approved replacement spec covers multiple subsystems: Papers, Research Workflow, Notes, QA, Compare, Knowledge Base, Agent, Monitor, Settings, and runtime integration. This plan intentionally covers only Slice 1 so the project has a working, testable foundation before the larger feature areas are migrated.

Future plans should cover:

- Slice 2: Papers upload, parse, index, delete, and detail route.
- Slice 3: Research Workflow and Zotero collection picker.
- Slice 4: Notes, QA, and Compare.
- Slice 5: Knowledge Base, Agent, and Monitor.
- Slice 6: docs, packaging, and optional FastAPI static mounting.

## Files And Responsibilities

Backend:

- Modify `app/schemas.py`: add typed response models for `/system/status`.
- Modify `app/main.py`: add a `GET /system/status` endpoint that aggregates existing health, vector-store, model, storage, Zotero config, Obsidian config, MCP Hub, papers, jobs, and research-run summary.
- Create `tests/test_system_status_endpoint.py`: verify response shape and degraded-safe behavior without loading heavy models.

Frontend scaffold:

- Create `frontend/package.json`: scripts and npm dependencies.
- Create `frontend/index.html`: Vite root document.
- Create `frontend/vite.config.ts`: React plugin, test environment, dev proxy to FastAPI.
- Create `frontend/tsconfig.json` and `frontend/tsconfig.node.json`: TypeScript config.
- Create `frontend/tailwind.config.ts` and `frontend/postcss.config.js`: Tailwind setup.
- Create `frontend/src/styles.css`: base theme, layout reset, accessible focus styles.
- Create `frontend/src/main.tsx`: React entrypoint.

Frontend app foundation:

- Create `frontend/src/app/queryClient.ts`: shared TanStack Query client.
- Create `frontend/src/app/providers.tsx`: app providers.
- Create `frontend/src/app/router.tsx`: route definitions for full replacement shell.
- Create `frontend/src/app/App.tsx`: router host.
- Create `frontend/src/stores/uiStore.ts`: UI-only state for sidebar collapse.

Frontend API layer:

- Create `frontend/src/api/client.ts`: typed fetch helper and API errors.
- Create `frontend/src/api/system.ts`: `/system/status` request and TypeScript response types.
- Create `frontend/src/api/papers.ts`: `GET /papers` request and response type.
- Create `frontend/src/api/tasks.ts`: `GET /tasks` request and response type.
- Create `frontend/src/api/researchRuns.ts`: `GET /research-runs` and `GET /research-runs/tools/health` response types.

Frontend components:

- Create `frontend/src/components/layout/AppLayout.tsx`: sidebar, topbar, content shell.
- Create `frontend/src/components/layout/navItems.ts`: navigation metadata.
- Create `frontend/src/components/status/StatusBadge.tsx`: shared status token.
- Create `frontend/src/components/status/MetricCard.tsx`: dashboard metric tile.
- Create `frontend/src/components/empty-state/EmptyState.tsx`: reusable empty state.
- Create `frontend/src/components/error-state/ErrorState.tsx`: reusable error state.

Frontend pages:

- Create `frontend/src/pages/dashboard/DashboardPage.tsx`: real-data dashboard.
- Create queued slice route components for `/workflow`, `/papers`, `/papers/:paperId`, `/notes`, `/qa`, `/compare`, `/knowledge-base`, `/agent`, `/monitor`, `/settings`; each queued slice must use the same layout and explain the next migration slice in one compact line.

Frontend tests:

- Create `frontend/src/test/setup.ts`: Testing Library setup.
- Create `frontend/src/api/system.test.ts`: API success and error tests.
- Create `frontend/src/components/status/StatusBadge.test.tsx`: status rendering tests.
- Create `frontend/src/pages/dashboard/DashboardPage.test.tsx`: dashboard loading, success, and error tests with mocked API calls.

Docs:

- Modify `docs/superpowers/plans/2026-06-18-react-frontend-slice1-plan.md` only while executing this plan checklist.
- Modify `README.md` only after Slice 1 passes, adding a short development-only React section that does not replace Streamlit as the primary entry.

## Task 1: Backend System Status Contract

**Files:**

- Modify: `app/schemas.py`
- Modify: `app/main.py`
- Test: `tests/test_system_status_endpoint.py`

- [ ] **Step 1: Write the failing backend API test**

Create `tests/test_system_status_endpoint.py`:

```python
from fastapi.testclient import TestClient

from app.main import app


def test_system_status_endpoint_returns_dashboard_contract(monkeypatch):
    from app import main

    class FakeVectorStore:
        def count(self):
            return 12

        def metadata(self):
            return {
                "backend": "json",
                "store_path": "app/storage/vector_db/vector_store.json",
                "chunk_count": 12,
            }

    class FakeJobStore:
        def list(self):
            return []

    class FakeResearchRunService:
        def list_runs(self):
            return []

    monkeypatch.setattr(main, "_get_vector_store", lambda: FakeVectorStore())
    monkeypatch.setattr(main, "_get_job_store", lambda: FakeJobStore())
    monkeypatch.setattr(main, "_get_research_run_service_for_status", lambda: FakeResearchRunService())
    monkeypatch.setattr(main, "list_papers", lambda metadata_dir: [{"paper_id": "paper_1", "title": "Paper 1", "abstract": "A"}])
    monkeypatch.setattr(main, "build_mcp_hub_health", lambda service, storage_root: [
        {
            "tool_name": "ResearchAgent MCP Server",
            "provider": "mcp_stdio",
            "available": True,
            "fallback_available": False,
            "fallback_active": False,
            "message": "available",
            "tool_count": 7,
            "state": "available",
        }
    ])

    client = TestClient(app)
    response = client.get("/system/status")

    assert response.status_code == 200
    payload = response.json()
    assert payload["project"] == "ResearchAgent"
    assert payload["status"] == "ok"
    assert payload["counts"] == {
        "papers": 1,
        "chunks": 12,
        "tasks": 0,
        "research_runs": 0,
    }
    assert payload["models"]["llm"]["configured"] is bool(main.settings.llm_api_key)
    assert payload["models"]["embedding"]["model"] == main.settings.embedding_model
    assert payload["vector_store"]["backend"] == "json"
    assert payload["integrations"]["zotero"]["local_api_url"] == "http://127.0.0.1:23119/api/users/0"
    assert payload["mcp_hub"][0]["tool_name"] == "ResearchAgent MCP Server"


def test_system_status_endpoint_degrades_when_vector_store_fails(monkeypatch):
    from app import main

    class BrokenVectorStore:
        def count(self):
            raise RuntimeError("vector store offline")

        def metadata(self):
            raise RuntimeError("vector store offline")

    class FakeJobStore:
        def list(self):
            return []

    class FakeResearchRunService:
        def list_runs(self):
            return []

    monkeypatch.setattr(main, "_get_vector_store", lambda: BrokenVectorStore())
    monkeypatch.setattr(main, "_get_job_store", lambda: FakeJobStore())
    monkeypatch.setattr(main, "_get_research_run_service_for_status", lambda: FakeResearchRunService())
    monkeypatch.setattr(main, "list_papers", lambda metadata_dir: [])
    monkeypatch.setattr(main, "build_mcp_hub_health", lambda service, storage_root: [])

    client = TestClient(app)
    response = client.get("/system/status")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "degraded"
    assert payload["vector_store"]["available"] is False
    assert payload["vector_store"]["error"] == "vector store offline"
```

- [ ] **Step 2: Run the backend test to verify it fails**

Run:

```powershell
& "D:\Hcworkspace\Anoconda3\envs\research_agent\python.exe" -m pytest tests/test_system_status_endpoint.py -q --basetemp .pytest-tmp-react-slice1-status
```

Expected: fail with an assertion or `404` because `GET /system/status` does not exist yet.

- [ ] **Step 3: Add response models to `app/schemas.py`**

Append these models near `HealthResponse`:

```python
class SystemStatusCounts(BaseModel):
    papers: int
    chunks: int
    tasks: int
    research_runs: int


class SystemStatusModelInfo(BaseModel):
    provider: str
    model: str
    configured: bool
    device: str | None = None
    batch_size: int | None = None


class SystemStatusVectorStore(BaseModel):
    available: bool
    backend: str | None = None
    store_path: str | None = None
    chunk_count: int = 0
    error: str | None = None


class SystemStatusStorage(BaseModel):
    upload_dir: str
    note_dir: str
    metadata_dir: str
    writable: bool


class SystemStatusIntegration(BaseModel):
    enabled: bool
    configured: bool
    local_api_url: str | None = None
    path: str | None = None


class SystemStatusResponse(BaseModel):
    project: str
    status: str
    counts: SystemStatusCounts
    models: dict[str, SystemStatusModelInfo]
    vector_store: SystemStatusVectorStore
    storage: SystemStatusStorage
    integrations: dict[str, SystemStatusIntegration]
    mcp_hub: list[dict[str, Any]]
```

- [ ] **Step 4: Add imports and helpers to `app/main.py`**

Add `SystemStatusResponse` to the `from app.schemas import (...)` list. Add imports near existing imports:

```python
from pathlib import Path

from app.research_workflow.mcp_health import build_mcp_hub_health
from app.research_workflow.service import ResearchRunService
from app.research_workflow.store import FileResearchRunStore
```

Add these helpers after `_resolve_upload_dir`:

```python
def _storage_is_writable() -> bool:
    for directory in [_resolve_upload_dir(), _resolve_note_dir(), _resolve_metadata_dir()]:
        try:
            os.makedirs(directory, exist_ok=True)
            probe = os.path.join(directory, ".system_status_probe")
            with open(probe, "w", encoding="utf-8") as f:
                f.write("ok")
            os.remove(probe)
        except OSError:
            return False
    return True


def _get_research_run_service_for_status() -> ResearchRunService:
    storage_root = Path(settings.metadata_dir).parent
    return ResearchRunService(
        store=FileResearchRunStore(storage_root / "research_runs.json"),
        vault_root=settings.obsidian_vault_root,
    )
```

- [ ] **Step 5: Implement `GET /system/status` in `app/main.py`**

Place this endpoint after `health_check`:

```python
@app.get("/system/status", response_model=SystemStatusResponse, summary="System status")
async def system_status():
    storage_root = Path(settings.metadata_dir).parent
    storage_writable = _storage_is_writable()

    vector_payload = {
        "available": True,
        "backend": None,
        "store_path": None,
        "chunk_count": 0,
        "error": None,
    }
    try:
        vector_store = _get_vector_store()
        vector_meta = vector_store.metadata()
        vector_payload.update(
            {
                "available": True,
                "backend": vector_meta.get("backend"),
                "store_path": vector_meta.get("store_path"),
                "chunk_count": int(vector_store.count()),
            }
        )
    except Exception as exc:
        vector_payload.update(
            {
                "available": False,
                "backend": None,
                "store_path": None,
                "chunk_count": 0,
                "error": str(exc),
            }
        )

    try:
        paper_count = len(list_papers(_resolve_metadata_dir()))
    except Exception:
        paper_count = 0

    try:
        task_count = len(_get_job_store().list())
    except Exception:
        task_count = 0

    try:
        research_service = _get_research_run_service_for_status()
        research_runs = research_service.list_runs()
        mcp_hub = build_mcp_hub_health(service=research_service, storage_root=storage_root)
    except Exception as exc:
        research_runs = []
        mcp_hub = [
            {
                "tool_name": "MCP Hub",
                "provider": "system",
                "available": False,
                "fallback_available": False,
                "fallback_active": False,
                "message": str(exc),
                "tool_count": 0,
                "state": "unavailable",
            }
        ]

    status = "ok" if storage_writable and vector_payload["available"] else "degraded"

    return SystemStatusResponse(
        project="ResearchAgent",
        status=status,
        counts={
            "papers": paper_count,
            "chunks": int(vector_payload["chunk_count"]),
            "tasks": task_count,
            "research_runs": len(research_runs),
        },
        models={
            "llm": {
                "provider": settings.llm_provider,
                "model": settings.llm_model,
                "configured": bool(settings.llm_api_key),
            },
            "embedding": {
                "provider": settings.embedding_provider,
                "model": settings.embedding_model,
                "configured": bool(settings.embedding_model),
                "device": settings.embedding_device,
                "batch_size": settings.embedding_batch_size,
            },
        },
        vector_store=vector_payload,
        storage={
            "upload_dir": settings.upload_dir,
            "note_dir": settings.note_dir,
            "metadata_dir": settings.metadata_dir,
            "writable": storage_writable,
        },
        integrations={
            "zotero": {
                "enabled": settings.enable_zotero or settings.zotero_local or settings.zotero_mcp_enabled,
                "configured": settings.zotero_local or bool(settings.zotero_mcp_command),
                "local_api_url": f"http://127.0.0.1:23119/api/users/{settings.zotero_library_id}",
            },
            "obsidian": {
                "enabled": bool(settings.obsidian_vault_root),
                "configured": bool(settings.obsidian_vault_root),
                "path": settings.obsidian_vault_root,
            },
        },
        mcp_hub=mcp_hub,
    )
```

- [ ] **Step 6: Run backend test to verify it passes**

Run:

```powershell
& "D:\Hcworkspace\Anoconda3\envs\research_agent\python.exe" -m pytest tests/test_system_status_endpoint.py -q --basetemp .pytest-tmp-react-slice1-status
```

Expected: `2 passed`.

- [ ] **Step 7: Commit backend status endpoint**

Run:

```powershell
git add app/schemas.py app/main.py tests/test_system_status_endpoint.py
git commit -m "feat: add system status endpoint"
```

## Task 2: Frontend Scaffold

**Files:**

- Create: `frontend/package.json`
- Create: `frontend/index.html`
- Create: `frontend/vite.config.ts`
- Create: `frontend/tsconfig.json`
- Create: `frontend/tsconfig.node.json`
- Create: `frontend/tailwind.config.ts`
- Create: `frontend/postcss.config.js`
- Create: `frontend/src/styles.css`
- Create: `frontend/src/main.tsx`
- Create: `frontend/src/app/App.tsx`
- Create: `frontend/src/app/providers.tsx`
- Create: `frontend/src/app/queryClient.ts`
- Create: `frontend/src/test/setup.ts`

- [ ] **Step 1: Create the frontend package manifest**

Create `frontend/package.json`:

```json
{
  "name": "research-agent-frontend",
  "private": true,
  "version": "0.1.0",
  "type": "module",
  "scripts": {
    "dev": "vite --host 127.0.0.1 --port 5173",
    "build": "tsc -b && vite build",
    "preview": "vite preview --host 127.0.0.1 --port 4173",
    "test": "vitest run",
    "test:watch": "vitest",
    "lint": "tsc -b --pretty false"
  },
  "dependencies": {
    "@tanstack/react-query": "^5.59.16",
    "clsx": "^2.1.1",
    "lucide-react": "^0.468.0",
    "react": "^18.3.1",
    "react-dom": "^18.3.1",
    "react-router-dom": "^6.28.0",
    "tailwind-merge": "^2.5.4",
    "zustand": "^5.0.1"
  },
  "devDependencies": {
    "@testing-library/jest-dom": "^6.6.3",
    "@testing-library/react": "^16.0.1",
    "@testing-library/user-event": "^14.5.2",
    "@types/node": "^22.9.0",
    "@types/react": "^18.3.12",
    "@types/react-dom": "^18.3.1",
    "@vitejs/plugin-react": "^4.3.3",
    "autoprefixer": "^10.4.20",
    "jsdom": "^25.0.1",
    "postcss": "^8.4.49",
    "tailwindcss": "^3.4.15",
    "typescript": "^5.6.3",
    "vite": "^5.4.11",
    "vitest": "^2.1.5"
  }
}
```

- [ ] **Step 2: Create Vite HTML entry**

Create `frontend/index.html`:

```html
<!doctype html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>ResearchAgent</title>
  </head>
  <body>
    <div id="root"></div>
    <script type="module" src="/src/main.tsx"></script>
  </body>
</html>
```

- [ ] **Step 3: Create Vite and TypeScript configs**

Create `frontend/vite.config.ts`:

```ts
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      "/api": "http://127.0.0.1:8888",
      "/agent": "http://127.0.0.1:8888",
      "/health": "http://127.0.0.1:8888",
      "/kb": "http://127.0.0.1:8888",
      "/library": "http://127.0.0.1:8888",
      "/papers": "http://127.0.0.1:8888",
      "/qa": "http://127.0.0.1:8888",
      "/research-runs": "http://127.0.0.1:8888",
      "/system": "http://127.0.0.1:8888",
      "/tasks": "http://127.0.0.1:8888"
    }
  },
  test: {
    environment: "jsdom",
    setupFiles: "./src/test/setup.ts",
    globals: true
  }
});
```

Create `frontend/tsconfig.json`:

```json
{
  "compilerOptions": {
    "target": "ES2020",
    "useDefineForClassFields": true,
    "lib": ["DOM", "DOM.Iterable", "ES2020"],
    "allowJs": false,
    "skipLibCheck": true,
    "esModuleInterop": true,
    "allowSyntheticDefaultImports": true,
    "strict": true,
    "forceConsistentCasingInFileNames": true,
    "module": "ESNext",
    "moduleResolution": "Node",
    "resolveJsonModule": true,
    "isolatedModules": true,
    "noEmit": true,
    "jsx": "react-jsx"
  },
  "include": ["src"],
  "references": [{ "path": "./tsconfig.node.json" }]
}
```

Create `frontend/tsconfig.node.json`:

```json
{
  "compilerOptions": {
    "composite": true,
    "module": "ESNext",
    "moduleResolution": "Node",
    "allowSyntheticDefaultImports": true
  },
  "include": ["vite.config.ts", "tailwind.config.ts"]
}
```

- [ ] **Step 4: Create Tailwind config and global CSS**

Create `frontend/tailwind.config.ts`:

```ts
import type { Config } from "tailwindcss";

export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        surface: "#f7f8fa",
        panel: "#ffffff",
        ink: "#172033",
        muted: "#667085",
        line: "#d9dee7",
        accent: "#2563eb"
      },
      boxShadow: {
        panel: "0 1px 2px rgba(16, 24, 40, 0.06)"
      }
    }
  },
  plugins: []
} satisfies Config;
```

Create `frontend/postcss.config.js`:

```js
export default {
  plugins: {
    tailwindcss: {},
    autoprefixer: {}
  }
};
```

Create `frontend/src/styles.css`:

```css
@tailwind base;
@tailwind components;
@tailwind utilities;

:root {
  color: #172033;
  background: #f7f8fa;
  font-family:
    Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI",
    sans-serif;
}

* {
  box-sizing: border-box;
}

body {
  margin: 0;
  min-width: 320px;
  min-height: 100vh;
}

button,
input,
select,
textarea {
  font: inherit;
}

:focus-visible {
  outline: 2px solid #2563eb;
  outline-offset: 2px;
}

@media (prefers-reduced-motion: reduce) {
  *,
  *::before,
  *::after {
    animation-duration: 0.01ms !important;
    animation-iteration-count: 1 !important;
    scroll-behavior: auto !important;
    transition-duration: 0.01ms !important;
  }
}
```

- [ ] **Step 5: Create React entry and providers**

Create `frontend/src/app/queryClient.ts`:

```ts
import { QueryClient } from "@tanstack/react-query";

export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 15_000,
      retry: 1,
      refetchOnWindowFocus: false
    }
  }
});
```

Create `frontend/src/app/providers.tsx`:

```tsx
import { QueryClientProvider } from "@tanstack/react-query";
import type { ReactNode } from "react";
import { queryClient } from "./queryClient";

interface ProvidersProps {
  children: ReactNode;
}

export function Providers({ children }: ProvidersProps) {
  return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>;
}
```

Create `frontend/src/app/App.tsx`:

```tsx
import { RouterProvider } from "react-router-dom";
import { router } from "./router";

export function App() {
  return <RouterProvider router={router} />;
}
```

Create `frontend/src/main.tsx`:

```tsx
import React from "react";
import ReactDOM from "react-dom/client";
import { App } from "./app/App";
import { Providers } from "./app/providers";
import "./styles.css";

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <Providers>
      <App />
    </Providers>
  </React.StrictMode>
);
```

Create `frontend/src/test/setup.ts`:

```ts
import "@testing-library/jest-dom/vitest";
```

- [ ] **Step 6: Install frontend dependencies**

Run:

```powershell
cd frontend
npm install
```

Expected: `package-lock.json` is created and npm exits with code 0.

- [ ] **Step 7: Run initial frontend checks**

Run:

```powershell
cd frontend
npm run lint
npm test
```

Expected: `npm run lint` passes; `npm test` exits successfully with no tests or the default Vitest pass state.

- [ ] **Step 8: Commit frontend scaffold**

Run:

```powershell
git add frontend
git commit -m "feat: scaffold react frontend"
```

## Task 3: Frontend API Layer

**Files:**

- Create: `frontend/src/api/client.ts`
- Create: `frontend/src/api/system.ts`
- Create: `frontend/src/api/papers.ts`
- Create: `frontend/src/api/tasks.ts`
- Create: `frontend/src/api/researchRuns.ts`
- Test: `frontend/src/api/system.test.ts`

- [ ] **Step 1: Write API client tests**

Create `frontend/src/api/system.test.ts`:

```ts
import { afterEach, describe, expect, it, vi } from "vitest";
import { ApiError } from "./client";
import { getSystemStatus } from "./system";

const okPayload = {
  project: "ResearchAgent",
  status: "ok",
  counts: { papers: 2, chunks: 10, tasks: 1, research_runs: 1 },
  models: {
    llm: { provider: "openai_compatible", model: "deepseek-chat", configured: true },
    embedding: {
      provider: "local",
      model: "bge-small-zh-v1.5",
      configured: true,
      device: "auto",
      batch_size: 32
    }
  },
  vector_store: {
    available: true,
    backend: "json",
    store_path: "app/storage/vector_db/vector_store.json",
    chunk_count: 10,
    error: null
  },
  storage: {
    upload_dir: "app/storage/papers",
    note_dir: "app/storage/notes",
    metadata_dir: "app/storage/metadata",
    writable: true
  },
  integrations: {
    zotero: {
      enabled: true,
      configured: true,
      local_api_url: "http://127.0.0.1:23119/api/users/0"
    },
    obsidian: {
      enabled: true,
      configured: true,
      path: "app/storage/knowledge_packs"
    }
  },
  mcp_hub: []
};

afterEach(() => {
  vi.restoreAllMocks();
});

describe("getSystemStatus", () => {
  it("returns typed system status JSON", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        json: async () => okPayload
      })
    );

    const result = await getSystemStatus();

    expect(fetch).toHaveBeenCalledWith("/system/status", {
      headers: { Accept: "application/json" }
    });
    expect(result.counts.papers).toBe(2);
    expect(result.models.embedding.batch_size).toBe(32);
  });

  it("throws ApiError with response detail on non-2xx status", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: false,
        status: 503,
        json: async () => ({ detail: "backend unavailable" })
      })
    );

    await expect(getSystemStatus()).rejects.toMatchObject({
      name: "ApiError",
      status: 503,
      message: "backend unavailable"
    } satisfies Partial<ApiError>);
  });
});
```

- [ ] **Step 2: Run API test to verify it fails**

Run:

```powershell
cd frontend
npm test -- src/api/system.test.ts
```

Expected: fail because `./client` and `./system` do not exist.

- [ ] **Step 3: Implement `frontend/src/api/client.ts`**

```ts
export class ApiError extends Error {
  status: number;

  constructor(message: string, status: number) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

export async function apiGet<T>(path: string): Promise<T> {
  const response = await fetch(path, {
    headers: { Accept: "application/json" }
  });

  if (!response.ok) {
    let message = response.statusText || `Request failed with ${response.status}`;
    try {
      const payload = (await response.json()) as { detail?: string; message?: string };
      message = payload.detail || payload.message || message;
    } catch {
      message = response.statusText || message;
    }
    throw new ApiError(message, response.status);
  }

  return (await response.json()) as T;
}
```

- [ ] **Step 4: Implement typed API modules**

Create `frontend/src/api/system.ts`:

```ts
import { apiGet } from "./client";

export interface SystemStatusCounts {
  papers: number;
  chunks: number;
  tasks: number;
  research_runs: number;
}

export interface SystemStatusModelInfo {
  provider: string;
  model: string;
  configured: boolean;
  device?: string | null;
  batch_size?: number | null;
}

export interface SystemStatusVectorStore {
  available: boolean;
  backend?: string | null;
  store_path?: string | null;
  chunk_count: number;
  error?: string | null;
}

export interface SystemStatusStorage {
  upload_dir: string;
  note_dir: string;
  metadata_dir: string;
  writable: boolean;
}

export interface SystemStatusIntegration {
  enabled: boolean;
  configured: boolean;
  local_api_url?: string | null;
  path?: string | null;
}

export interface McpHealthItem {
  tool_name: string;
  provider: string;
  available: boolean;
  fallback_available: boolean;
  fallback_active: boolean;
  message: string;
  tool_count?: number | null;
  state: string;
}

export interface SystemStatus {
  project: string;
  status: string;
  counts: SystemStatusCounts;
  models: Record<string, SystemStatusModelInfo>;
  vector_store: SystemStatusVectorStore;
  storage: SystemStatusStorage;
  integrations: Record<string, SystemStatusIntegration>;
  mcp_hub: McpHealthItem[];
}

export function getSystemStatus() {
  return apiGet<SystemStatus>("/system/status");
}
```

Create `frontend/src/api/papers.ts`:

```ts
import { apiGet } from "./client";

export interface PaperListItem {
  paper_id: string;
  title: string;
  abstract: string;
}

export interface PaperListResponse {
  count: number;
  papers: PaperListItem[];
}

export function getPapers() {
  return apiGet<PaperListResponse>("/papers");
}
```

Create `frontend/src/api/tasks.ts`:

```ts
import { apiGet } from "./client";

export interface TaskStatus {
  job_id: string;
  job_type: string;
  paper_id?: string | null;
  paper_ids?: string[] | null;
  status: "queued" | "running" | "completed" | "failed" | "cancelled";
  progress: number;
  error?: string | null;
  result?: Record<string, unknown> | null;
}

export interface TaskListResponse {
  count: number;
  jobs: TaskStatus[];
}

export function getTasks() {
  return apiGet<TaskListResponse>("/tasks");
}
```

Create `frontend/src/api/researchRuns.ts`:

```ts
import { apiGet } from "./client";
import type { McpHealthItem } from "./system";

export interface ResearchRunStep {
  agent: string;
  status: string;
  progress: number;
}

export interface ResearchRun {
  run_id: string;
  collection_id: string;
  collection_name: string;
  goal: string;
  status: string;
  progress: number;
  steps: ResearchRunStep[];
  error?: string | null;
}

export interface ResearchRunListResponse {
  count: number;
  runs: ResearchRun[];
}

export interface ResearchRunToolsHealthResponse {
  tools: McpHealthItem[];
}

export function getResearchRuns() {
  return apiGet<ResearchRunListResponse>("/research-runs");
}

export function getResearchRunToolsHealth() {
  return apiGet<ResearchRunToolsHealthResponse>("/research-runs/tools/health");
}
```

- [ ] **Step 5: Run API tests**

Run:

```powershell
cd frontend
npm test -- src/api/system.test.ts
npm run lint
```

Expected: both commands pass.

- [ ] **Step 6: Commit frontend API layer**

Run:

```powershell
git add frontend/src/api
git commit -m "feat: add frontend api client"
```

## Task 4: Layout, Routing, And UI State

**Files:**

- Create: `frontend/src/components/layout/navItems.ts`
- Create: `frontend/src/components/layout/AppLayout.tsx`
- Create: `frontend/src/stores/uiStore.ts`
- Create: `frontend/src/app/router.tsx`
- Create queued slice page files under `frontend/src/pages/*`

- [ ] **Step 1: Create UI store**

Create `frontend/src/stores/uiStore.ts`:

```ts
import { create } from "zustand";

interface UiState {
  sidebarCollapsed: boolean;
  toggleSidebar: () => void;
}

export const useUiStore = create<UiState>((set) => ({
  sidebarCollapsed: false,
  toggleSidebar: () => set((state) => ({ sidebarCollapsed: !state.sidebarCollapsed }))
}));
```

- [ ] **Step 2: Create navigation metadata**

Create `frontend/src/components/layout/navItems.ts`:

```ts
import {
  Activity,
  Bot,
  Brain,
  Files,
  GitCompare,
  Home,
  Library,
  MessageSquare,
  NotebookText,
  Settings,
  Workflow
} from "lucide-react";
import type { ComponentType } from "react";

export interface NavItem {
  label: string;
  path: string;
  icon: ComponentType<{ className?: string }>;
}

export const navItems: NavItem[] = [
  { label: "Dashboard", path: "/dashboard", icon: Home },
  { label: "Workflow", path: "/workflow", icon: Workflow },
  { label: "Papers", path: "/papers", icon: Files },
  { label: "Notes", path: "/notes", icon: NotebookText },
  { label: "QA", path: "/qa", icon: MessageSquare },
  { label: "Compare", path: "/compare", icon: GitCompare },
  { label: "Knowledge Base", path: "/knowledge-base", icon: Library },
  { label: "Agent", path: "/agent", icon: Bot },
  { label: "Monitor", path: "/monitor", icon: Activity },
  { label: "Settings", path: "/settings", icon: Settings }
];

export const appIcon = Brain;
```

- [ ] **Step 3: Create queued slice page component helper**

Create `frontend/src/pages/QueuedSlicePage.tsx`:

```tsx
interface QueuedSlicePageProps {
  title: string;
  description: string;
}

export function QueuedSlicePage({ title, description }: QueuedSlicePageProps) {
  return (
    <section className="rounded-md border border-line bg-panel p-6 shadow-panel">
      <p className="text-sm font-medium text-accent">Migration slice queued</p>
      <h1 className="mt-2 text-2xl font-semibold text-ink">{title}</h1>
      <p className="mt-2 max-w-3xl text-sm leading-6 text-muted">{description}</p>
    </section>
  );
}
```

- [ ] **Step 4: Create layout shell**

Create `frontend/src/components/layout/AppLayout.tsx`:

```tsx
import { Menu } from "lucide-react";
import { NavLink, Outlet } from "react-router-dom";
import { useUiStore } from "../../stores/uiStore";
import { appIcon as AppIcon, navItems } from "./navItems";

export function AppLayout() {
  const sidebarCollapsed = useUiStore((state) => state.sidebarCollapsed);
  const toggleSidebar = useUiStore((state) => state.toggleSidebar);

  return (
    <div className="min-h-screen bg-surface text-ink">
      <aside
        className={`fixed inset-y-0 left-0 z-20 border-r border-line bg-panel transition-all ${
          sidebarCollapsed ? "w-16" : "w-64"
        }`}
        aria-label="Primary navigation"
      >
        <div className="flex h-14 items-center gap-3 border-b border-line px-4">
          <AppIcon className="h-5 w-5 text-accent" aria-hidden="true" />
          {!sidebarCollapsed && <span className="text-sm font-semibold">ResearchAgent</span>}
        </div>
        <nav className="space-y-1 p-2">
          {navItems.map((item) => (
            <NavLink
              key={item.path}
              to={item.path}
              className={({ isActive }) =>
                [
                  "flex h-10 items-center gap-3 rounded-md px-3 text-sm font-medium",
                  isActive ? "bg-blue-50 text-accent" : "text-muted hover:bg-surface hover:text-ink"
                ].join(" ")
              }
              title={sidebarCollapsed ? item.label : undefined}
            >
              <item.icon className="h-4 w-4 shrink-0" aria-hidden="true" />
              {!sidebarCollapsed && <span>{item.label}</span>}
            </NavLink>
          ))}
        </nav>
      </aside>

      <div className={sidebarCollapsed ? "pl-16" : "pl-64"}>
        <header className="sticky top-0 z-10 flex h-14 items-center justify-between border-b border-line bg-panel px-6">
          <button
            type="button"
            className="inline-flex h-9 w-9 items-center justify-center rounded-md border border-line text-muted hover:bg-surface hover:text-ink"
            onClick={toggleSidebar}
            aria-label="Toggle sidebar"
          >
            <Menu className="h-4 w-4" aria-hidden="true" />
          </button>
          <div className="text-sm text-muted">FastAPI backend: 127.0.0.1:8888</div>
        </header>
        <main className="p-6">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
```

- [ ] **Step 5: Create router and queued slice pages**

Create `frontend/src/pages/workflow/WorkflowPage.tsx`:

```tsx
import { QueuedSlicePage } from "../QueuedSlicePage";

export function WorkflowPage() {
  return (
    <QueuedSlicePage
      title="Research Workflow"
      description="Next migration slice: Zotero collections, research runs, MCP Hub, Agent Timeline, paper items, and Knowledge Pack outputs."
    />
  );
}
```

Create similar files with exact content:

`frontend/src/pages/papers/PapersPage.tsx`:

```tsx
import { QueuedSlicePage } from "../QueuedSlicePage";

export function PapersPage() {
  return (
    <QueuedSlicePage
      title="Papers"
      description="Next migration slice: multi-PDF upload, parse, index, delete confirmation, paper search, and table filtering."
    />
  );
}
```

`frontend/src/pages/paper-detail/PaperDetailPage.tsx`:

```tsx
import { useParams } from "react-router-dom";
import { QueuedSlicePage } from "../QueuedSlicePage";

export function PaperDetailPage() {
  const { paperId } = useParams();
  return (
    <QueuedSlicePage
      title={`Paper Detail${paperId ? `: ${paperId}` : ""}`}
      description="Next migration slice: parsed metadata, note status, index status, sections, source chunks, and paper-scoped QA."
    />
  );
}
```

`frontend/src/pages/notes/NotesPage.tsx`:

```tsx
import { QueuedSlicePage } from "../QueuedSlicePage";

export function NotesPage() {
  return (
    <QueuedSlicePage
      title="Notes"
      description="Next migration slice: note generation tasks, Markdown preview, and download."
    />
  );
}
```

`frontend/src/pages/qa/QaPage.tsx`:

```tsx
import { QueuedSlicePage } from "../QueuedSlicePage";

export function QaPage() {
  return (
    <QueuedSlicePage
      title="QA"
      description="Next migration slice: whole-library and single-paper QA with answer sources and citation chunks."
    />
  );
}
```

`frontend/src/pages/compare/ComparePage.tsx`:

```tsx
import { QueuedSlicePage } from "../QueuedSlicePage";

export function ComparePage() {
  return (
    <QueuedSlicePage
      title="Compare"
      description="Next migration slice: select two to five papers, run comparison, preview Markdown, and download output."
    />
  );
}
```

`frontend/src/pages/knowledge-base/KnowledgeBasePage.tsx`:

```tsx
import { QueuedSlicePage } from "../QueuedSlicePage";

export function KnowledgeBasePage() {
  return (
    <QueuedSlicePage
      title="Knowledge Base"
      description="Next migration slice: list knowledge bases, create knowledge bases, and add or remove papers."
    />
  );
}
```

`frontend/src/pages/agent/AgentPage.tsx`:

```tsx
import { QueuedSlicePage } from "../QueuedSlicePage";

export function AgentPage() {
  return (
    <QueuedSlicePage
      title="Agent"
      description="Next migration slice: supervisor/react chat modes and dedicated paper analysis workflows."
    />
  );
}
```

`frontend/src/pages/monitor/MonitorPage.tsx`:

```tsx
import { QueuedSlicePage } from "../QueuedSlicePage";

export function MonitorPage() {
  return (
    <QueuedSlicePage
      title="Monitor"
      description="Next migration slice: traces, routing decisions, tool-call statistics, latency, and filterable events."
    />
  );
}
```

`frontend/src/pages/settings/SettingsPage.tsx`:

```tsx
import { QueuedSlicePage } from "../QueuedSlicePage";

export function SettingsPage() {
  return (
    <QueuedSlicePage
      title="Settings"
      description="Next migration slice: runtime configuration, model status, Zotero, Obsidian, and backend connection details."
    />
  );
}
```

Create `frontend/src/app/router.tsx`:

```tsx
import { Navigate, createBrowserRouter } from "react-router-dom";
import { AppLayout } from "../components/layout/AppLayout";
import { AgentPage } from "../pages/agent/AgentPage";
import { ComparePage } from "../pages/compare/ComparePage";
import { DashboardPage } from "../pages/dashboard/DashboardPage";
import { KnowledgeBasePage } from "../pages/knowledge-base/KnowledgeBasePage";
import { MonitorPage } from "../pages/monitor/MonitorPage";
import { NotesPage } from "../pages/notes/NotesPage";
import { PaperDetailPage } from "../pages/paper-detail/PaperDetailPage";
import { PapersPage } from "../pages/papers/PapersPage";
import { QaPage } from "../pages/qa/QaPage";
import { SettingsPage } from "../pages/settings/SettingsPage";
import { WorkflowPage } from "../pages/workflow/WorkflowPage";

export const router = createBrowserRouter([
  {
    path: "/",
    element: <AppLayout />,
    children: [
      { index: true, element: <Navigate to="/dashboard" replace /> },
      { path: "dashboard", element: <DashboardPage /> },
      { path: "workflow", element: <WorkflowPage /> },
      { path: "papers", element: <PapersPage /> },
      { path: "papers/:paperId", element: <PaperDetailPage /> },
      { path: "notes", element: <NotesPage /> },
      { path: "qa", element: <QaPage /> },
      { path: "compare", element: <ComparePage /> },
      { path: "knowledge-base", element: <KnowledgeBasePage /> },
      { path: "agent", element: <AgentPage /> },
      { path: "monitor", element: <MonitorPage /> },
      { path: "settings", element: <SettingsPage /> }
    ]
  }
]);
```

- [ ] **Step 6: Run typecheck**

Run:

```powershell
cd frontend
npm run lint
```

Expected: pass.

- [ ] **Step 7: Commit layout and routes**

Run:

```powershell
git add frontend/src/app frontend/src/components/layout frontend/src/pages frontend/src/stores
git commit -m "feat: add react workspace shell"
```

## Task 5: Status Components And Dashboard

**Files:**

- Create: `frontend/src/components/status/StatusBadge.tsx`
- Create: `frontend/src/components/status/MetricCard.tsx`
- Create: `frontend/src/components/empty-state/EmptyState.tsx`
- Create: `frontend/src/components/error-state/ErrorState.tsx`
- Create: `frontend/src/pages/dashboard/DashboardPage.tsx`
- Test: `frontend/src/components/status/StatusBadge.test.tsx`
- Test: `frontend/src/pages/dashboard/DashboardPage.test.tsx`

- [ ] **Step 1: Write status badge test**

Create `frontend/src/components/status/StatusBadge.test.tsx`:

```tsx
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { StatusBadge } from "./StatusBadge";

describe("StatusBadge", () => {
  it("renders fallback active state with accessible text", () => {
    render(<StatusBadge status="fallback_active" />);
    expect(screen.getByText("fallback active")).toBeInTheDocument();
  });

  it("renders failed state with alert tone", () => {
    render(<StatusBadge status="failed" label="failed" />);
    expect(screen.getByText("failed")).toHaveClass("bg-red-50");
  });
});
```

- [ ] **Step 2: Run status badge test to verify it fails**

Run:

```powershell
cd frontend
npm test -- src/components/status/StatusBadge.test.tsx
```

Expected: fail because `StatusBadge` does not exist.

- [ ] **Step 3: Implement shared status and support components**

Create `frontend/src/components/status/StatusBadge.tsx`:

```tsx
import { clsx } from "clsx";

const toneByStatus: Record<string, string> = {
  ok: "bg-emerald-50 text-emerald-700 ring-emerald-200",
  available: "bg-emerald-50 text-emerald-700 ring-emerald-200",
  completed: "bg-emerald-50 text-emerald-700 ring-emerald-200",
  running: "bg-blue-50 text-blue-700 ring-blue-200",
  queued: "bg-slate-50 text-slate-700 ring-slate-200",
  degraded: "bg-amber-50 text-amber-700 ring-amber-200",
  fallback_active: "bg-amber-50 text-amber-700 ring-amber-200",
  unavailable: "bg-red-50 text-red-700 ring-red-200",
  failed: "bg-red-50 text-red-700 ring-red-200",
  cancelled: "bg-slate-100 text-slate-600 ring-slate-200"
};

interface StatusBadgeProps {
  status: string;
  label?: string;
}

export function StatusBadge({ status, label }: StatusBadgeProps) {
  const normalized = status.replaceAll("_", " ");
  return (
    <span
      className={clsx(
        "inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ring-1 ring-inset",
        toneByStatus[status] ?? "bg-slate-50 text-slate-700 ring-slate-200"
      )}
    >
      {label ?? normalized}
    </span>
  );
}
```

Create `frontend/src/components/status/MetricCard.tsx`:

```tsx
interface MetricCardProps {
  label: string;
  value: string | number;
  detail?: string;
}

export function MetricCard({ label, value, detail }: MetricCardProps) {
  return (
    <div className="rounded-md border border-line bg-panel p-4 shadow-panel">
      <p className="text-sm text-muted">{label}</p>
      <p className="mt-2 text-2xl font-semibold text-ink">{value}</p>
      {detail ? <p className="mt-1 text-xs text-muted">{detail}</p> : null}
    </div>
  );
}
```

Create `frontend/src/components/empty-state/EmptyState.tsx`:

```tsx
interface EmptyStateProps {
  title: string;
  description: string;
}

export function EmptyState({ title, description }: EmptyStateProps) {
  return (
    <div className="rounded-md border border-dashed border-line bg-panel p-6 text-center">
      <h2 className="text-sm font-semibold text-ink">{title}</h2>
      <p className="mt-1 text-sm text-muted">{description}</p>
    </div>
  );
}
```

Create `frontend/src/components/error-state/ErrorState.tsx`:

```tsx
interface ErrorStateProps {
  title: string;
  message: string;
}

export function ErrorState({ title, message }: ErrorStateProps) {
  return (
    <div role="alert" className="rounded-md border border-red-200 bg-red-50 p-4 text-red-800">
      <h2 className="text-sm font-semibold">{title}</h2>
      <p className="mt-1 text-sm">{message}</p>
    </div>
  );
}
```

- [ ] **Step 4: Write dashboard tests**

Create `frontend/src/pages/dashboard/DashboardPage.test.tsx`:

```tsx
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { DashboardPage } from "./DashboardPage";

function renderWithQuery(ui: React.ReactElement) {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } }
  });
  return render(<QueryClientProvider client={client}>{ui}</QueryClientProvider>);
}

const statusPayload = {
  project: "ResearchAgent",
  status: "ok",
  counts: { papers: 3, chunks: 21, tasks: 2, research_runs: 1 },
  models: {
    llm: { provider: "openai_compatible", model: "deepseek-chat", configured: true },
    embedding: {
      provider: "local",
      model: "bge-small-zh-v1.5",
      configured: true,
      device: "auto",
      batch_size: 32
    }
  },
  vector_store: { available: true, backend: "json", store_path: "store.json", chunk_count: 21, error: null },
  storage: {
    upload_dir: "app/storage/papers",
    note_dir: "app/storage/notes",
    metadata_dir: "app/storage/metadata",
    writable: true
  },
  integrations: {
    zotero: { enabled: true, configured: true, local_api_url: "http://127.0.0.1:23119/api/users/0" },
    obsidian: { enabled: true, configured: true, path: "app/storage/knowledge_packs" }
  },
  mcp_hub: [
    {
      tool_name: "ResearchAgent MCP Server",
      provider: "mcp_stdio",
      available: true,
      fallback_available: false,
      fallback_active: false,
      message: "available",
      tool_count: 7,
      state: "available"
    }
  ]
};

afterEach(() => {
  vi.restoreAllMocks();
});

describe("DashboardPage", () => {
  it("renders system metrics from backend data", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        json: async () => statusPayload
      })
    );

    renderWithQuery(<DashboardPage />);

    expect(screen.getByText("Loading dashboard")).toBeInTheDocument();
    await waitFor(() => expect(screen.getByText("ResearchAgent")).toBeInTheDocument());
    expect(screen.getByText("3")).toBeInTheDocument();
    expect(screen.getByText("21")).toBeInTheDocument();
    expect(screen.getByText("ResearchAgent MCP Server")).toBeInTheDocument();
    expect(screen.getByText("deepseek-chat")).toBeInTheDocument();
  });

  it("renders an error state when the backend fails", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("network down")));

    renderWithQuery(<DashboardPage />);

    await waitFor(() => expect(screen.getByRole("alert")).toBeInTheDocument());
    expect(screen.getByText("Unable to load dashboard")).toBeInTheDocument();
  });
});
```

- [ ] **Step 5: Run dashboard test to verify it fails**

Run:

```powershell
cd frontend
npm test -- src/pages/dashboard/DashboardPage.test.tsx
```

Expected: fail because `DashboardPage` has not been implemented.

- [ ] **Step 6: Implement dashboard page**

Create `frontend/src/pages/dashboard/DashboardPage.tsx`:

```tsx
import { useQuery } from "@tanstack/react-query";
import { Activity, Database, FileText, Workflow } from "lucide-react";
import { getSystemStatus } from "../../api/system";
import { EmptyState } from "../../components/empty-state/EmptyState";
import { ErrorState } from "../../components/error-state/ErrorState";
import { MetricCard } from "../../components/status/MetricCard";
import { StatusBadge } from "../../components/status/StatusBadge";

export function DashboardPage() {
  const { data, isLoading, error } = useQuery({
    queryKey: ["system-status"],
    queryFn: getSystemStatus
  });

  if (isLoading) {
    return <p className="text-sm text-muted">Loading dashboard</p>;
  }

  if (error) {
    return <ErrorState title="Unable to load dashboard" message={(error as Error).message} />;
  }

  if (!data) {
    return <EmptyState title="No status data" description="The backend returned an empty system status response." />;
  }

  const llm = data.models.llm;
  const embedding = data.models.embedding;

  return (
    <div className="space-y-6">
      <section className="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
        <div>
          <p className="text-sm font-medium text-accent">React Workspace</p>
          <h1 className="mt-1 text-3xl font-semibold text-ink">{data.project}</h1>
          <p className="mt-2 max-w-3xl text-sm leading-6 text-muted">
            Developer-console view for research runs, paper knowledge, MCP health, and agent activity.
          </p>
        </div>
        <StatusBadge status={data.status} />
      </section>

      <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-4" aria-label="System metrics">
        <MetricCard label="Papers" value={data.counts.papers} detail="Parsed metadata records" />
        <MetricCard label="Indexed chunks" value={data.counts.chunks} detail={data.vector_store.backend ?? "No vector backend"} />
        <MetricCard label="Background tasks" value={data.counts.tasks} detail="Queued, running, and recent jobs" />
        <MetricCard label="Research runs" value={data.counts.research_runs} detail="Zotero-driven workflow runs" />
      </section>

      <section className="grid gap-4 xl:grid-cols-[1fr_1.4fr]">
        <div className="rounded-md border border-line bg-panel p-4 shadow-panel">
          <div className="flex items-center gap-2">
            <Activity className="h-4 w-4 text-accent" aria-hidden="true" />
            <h2 className="text-sm font-semibold text-ink">Runtime</h2>
          </div>
          <dl className="mt-4 space-y-3 text-sm">
            <div className="flex items-center justify-between gap-4">
              <dt className="text-muted">LLM</dt>
              <dd className="font-medium text-ink">{llm.model}</dd>
            </div>
            <div className="flex items-center justify-between gap-4">
              <dt className="text-muted">Embedding</dt>
              <dd className="font-medium text-ink">{embedding.model}</dd>
            </div>
            <div className="flex items-center justify-between gap-4">
              <dt className="text-muted">Storage writable</dt>
              <dd>
                <StatusBadge status={data.storage.writable ? "ok" : "failed"} label={data.storage.writable ? "yes" : "no"} />
              </dd>
            </div>
            <div className="flex items-center justify-between gap-4">
              <dt className="text-muted">Vector store</dt>
              <dd>
                <StatusBadge status={data.vector_store.available ? "available" : "unavailable"} />
              </dd>
            </div>
          </dl>
        </div>

        <div className="rounded-md border border-line bg-panel p-4 shadow-panel">
          <div className="flex items-center gap-2">
            <Database className="h-4 w-4 text-accent" aria-hidden="true" />
            <h2 className="text-sm font-semibold text-ink">MCP Hub</h2>
          </div>
          <div className="mt-4 divide-y divide-line">
            {data.mcp_hub.length === 0 ? (
              <EmptyState title="No MCP health records" description="The backend returned no tool health rows." />
            ) : (
              data.mcp_hub.map((tool) => (
                <div key={`${tool.tool_name}-${tool.provider}`} className="flex items-start justify-between gap-4 py-3">
                  <div>
                    <p className="text-sm font-medium text-ink">{tool.tool_name}</p>
                    <p className="mt-1 text-xs text-muted">{tool.provider}: {tool.message}</p>
                  </div>
                  <StatusBadge status={tool.state} />
                </div>
              ))
            )}
          </div>
        </div>
      </section>

      <section className="grid gap-4 xl:grid-cols-2">
        <div className="rounded-md border border-line bg-panel p-4 shadow-panel">
          <div className="flex items-center gap-2">
            <FileText className="h-4 w-4 text-accent" aria-hidden="true" />
            <h2 className="text-sm font-semibold text-ink">Paper Knowledge</h2>
          </div>
          <p className="mt-3 text-sm leading-6 text-muted">
            Papers, notes, QA, comparison, and knowledge-base views are wired into the shell and will be migrated on top of this API foundation.
          </p>
        </div>
        <div className="rounded-md border border-line bg-panel p-4 shadow-panel">
          <div className="flex items-center gap-2">
            <Workflow className="h-4 w-4 text-accent" aria-hidden="true" />
            <h2 className="text-sm font-semibold text-ink">Workflow Console</h2>
          </div>
          <p className="mt-3 text-sm leading-6 text-muted">
            Research Workflow will use Zotero collection intake, research runs, Agent Timeline, Knowledge Pack outputs, and MCP Hub status.
          </p>
        </div>
      </section>
    </div>
  );
}
```

- [ ] **Step 7: Run component and dashboard tests**

Run:

```powershell
cd frontend
npm test -- src/components/status/StatusBadge.test.tsx src/pages/dashboard/DashboardPage.test.tsx
npm run lint
```

Expected: all tests and typecheck pass.

- [ ] **Step 8: Commit dashboard slice**

Run:

```powershell
git add frontend/src/components frontend/src/pages/dashboard
git commit -m "feat: add react dashboard"
```

## Task 6: Slice 1 Documentation And Verification

**Files:**

- Modify: `README.md`
- Verify: backend tests, frontend tests, frontend build.

- [ ] **Step 1: Add development-only React instructions to `README.md`**

Add this section near the existing startup instructions:

```markdown
### React Frontend Preview

The React frontend is being introduced as a staged replacement for the Streamlit UI. During migration, Streamlit remains available and React runs as a separate development server.

Start the FastAPI backend:

```powershell
uvicorn app.main:app --reload --port 8888
```

Start the React frontend:

```powershell
cd frontend
npm install
npm run dev
```

Open:

```text
http://127.0.0.1:5173
```

The first React slice includes the workspace shell and dashboard. Streamlit remains the primary documented end-user path until the React Papers, Workflow, QA, Compare, Agent, and Monitor pages reach parity.
```

- [ ] **Step 2: Run backend verification**

Run:

```powershell
& "D:\Hcworkspace\Anoconda3\envs\research_agent\python.exe" -m pytest tests/test_system_status_endpoint.py tests/test_research_workflow_ui_import.py -q --basetemp .pytest-tmp-react-slice1-final
```

Expected: tests pass. This verifies the new backend endpoint and that the existing Streamlit Research Workflow wiring still has its guard tests.

- [ ] **Step 3: Run frontend verification**

Run:

```powershell
cd frontend
npm test
npm run lint
npm run build
```

Expected: Vitest, TypeScript, and Vite build pass.

- [ ] **Step 4: Inspect final diff scope**

Run:

```powershell
git status --short
git diff --stat
```

Expected: only intended files from this plan are modified or created. Existing unrelated dirty/deleted files may still appear; do not revert them.

- [ ] **Step 5: Commit docs and final verification changes**

Run:

```powershell
git add README.md docs/superpowers/plans/2026-06-18-react-frontend-slice1-plan.md
git commit -m "docs: add react frontend slice one plan"
```

If the plan file was already committed before execution, commit only `README.md`:

```powershell
git add README.md
git commit -m "docs: document react frontend preview"
```

## Plan Self-Review

Spec coverage:

- App shell and API foundation are covered by Tasks 1-5.
- `/dashboard` is covered by Task 5.
- `GET /system/status` is covered by Task 1.
- Two-service local development documentation is covered by Task 6.
- Streamlit preservation is covered by backend verification and docs language.
- Full replacement routes are present as queued slice pages in Task 4, with real implementations deferred to future slice plans.

Red-flag scan:

- The plan avoids unfinished-marker words and unspecified "add error handling" steps.
- Each implementation task includes explicit files, commands, and expected results.

Type consistency:

- Backend response fields use snake_case to match JSON emitted by Pydantic.
- Frontend TypeScript interfaces use the same snake_case fields.
- Dashboard reads `counts.research_runs`, `vector_store.chunk_count`, and `models.embedding.batch_size`, matching the backend contract.
