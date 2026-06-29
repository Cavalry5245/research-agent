# Research Sets Step 2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn the current Knowledge Base page into a user-facing "Research Sets" experience with auto IDs, searchable paper selection, useful set stats, and downstream entry points.

**Architecture:** Keep existing `/kb` endpoints and `KnowledgeBaseManager` as the compatibility layer. Add backend-generated IDs and derived stats first, then update the frontend API contract, then rebuild the page around research-set cards and a searchable multi-select picker. Keep the change reversible by preserving old `kb_id` input support in the backend.

**Tech Stack:** FastAPI + Pydantic, JSON-backed `KnowledgeBaseManager`, React + TypeScript + TanStack Query, Vitest + Testing Library, Tailwind CSS.

---

## File Structure

- Modify `app/services/knowledge_base_manager.py`
  - Normalize old registry entries.
  - Generate unique IDs from set names.
  - Maintain `updated_at` on membership changes.
- Modify `app/schemas.py`
  - Make `KBCreateRequest.kb_id` optional.
  - Extend `KBResponse` with optional derived stats.
- Modify `app/main.py`
  - Allow `/kb` creation without `kb_id`.
  - Enrich `/kb` list/create/add/remove responses with stats.
- Modify `tests/test_kb_management.py`
  - Cover auto ID generation, duplicate suffixes, and `updated_at`.
- Modify `tests/test_kb_endpoints.py`
  - Cover create-without-ID and enriched response fields.
- Modify `frontend/src/api/types.ts`
  - Extend `KnowledgeBase`.
  - Add `KnowledgeBaseCreatePayload`.
- Modify `frontend/src/api/knowledgeBase.ts`
  - Stop requiring `kb_id`.
  - Add `addPapersToKnowledgeBase`.
- Create `frontend/src/pages/knowledge-base/researchSetUtils.ts`
  - Derive member papers, available papers, percentages, and dates.
- Create `frontend/src/pages/knowledge-base/ResearchSetPaperPicker.tsx`
  - Searchable multi-select paper picker.
- Modify `frontend/src/pages/knowledge-base/KnowledgeBasePage.tsx`
  - Replace old Knowledge Base form and copy with Research Sets UX.
- Modify `frontend/src/pages/knowledge-base/KnowledgeBasePage.test.tsx`
  - Cover creation, search-select add, member title display, and removal.
- Modify `frontend/src/components/layout/navItems.ts`
  - Rename sidebar label to `Research Sets`.

---

### Task 1: Backend Creation Contract

**Files:**
- Modify: `app/services/knowledge_base_manager.py`
- Modify: `app/schemas.py`
- Modify: `app/main.py`
- Test: `tests/test_kb_management.py`
- Test: `tests/test_kb_endpoints.py`

- [ ] **Step 1: Add manager tests for generated IDs**

In `tests/test_kb_management.py`, add tests equivalent to:

```python
def test_create_kb_generates_slug_id_when_missing(tmp_path):
    mgr = KnowledgeBaseManager(tmp_path / "kbs.json")

    kb = mgr.create_kb(None, "Graph RAG", "retrieval papers")

    assert kb["id"] == "graph-rag"
    assert kb["name"] == "Graph RAG"
    assert kb["description"] == "retrieval papers"
    assert kb["paper_ids"] == []
    assert kb["created_at"]
    assert kb["updated_at"]


def test_create_kb_generates_unique_suffix(tmp_path):
    mgr = KnowledgeBaseManager(tmp_path / "kbs.json")

    first = mgr.create_kb(None, "Graph RAG")
    second = mgr.create_kb(None, "Graph RAG")

    assert first["id"] == "graph-rag"
    assert second["id"] == "graph-rag-2"
```

- [ ] **Step 2: Run tests and confirm failure**

Run:

```powershell
& 'D:\Hcworkspace\Anoconda3\envs\research_agent\python.exe' -m pytest tests/test_kb_management.py -q
```

Expected: fails because `create_kb` currently requires `kb_id: str`.

- [ ] **Step 3: Implement manager normalization and ID generation**

In `app/services/knowledge_base_manager.py`:

```python
import re


def _slugify_name(name: str) -> str:
    value = re.sub(r"[^a-zA-Z0-9\u4e00-\u9fff]+", "-", name.strip().lower()).strip("-")
    return value or "research-set"


def _normalize_entry(entry: dict) -> dict:
    now = utc_now_iso()
    entry.setdefault("description", "")
    entry.setdefault("paper_ids", [])
    entry.setdefault("created_at", now)
    entry.setdefault("updated_at", entry.get("created_at") or now)
    return entry
```

Update `_load()` so both default and JSON-loaded records pass through `_normalize_entry()`.

- [ ] **Step 4: Change `create_kb` without recursive lock risk**

Do not call a `_load()`-based `generate_kb_id()` while already holding `self._lock`. Use an internal helper:

```python
def _generate_kb_id_from_data(self, data: dict, name: str) -> str:
    existing = set(data.get("knowledge_bases", {}))
    base = _slugify_name(name)
    candidate = base
    suffix = 2
    while candidate in existing:
        candidate = f"{base}-{suffix}"
        suffix += 1
    return candidate


def create_kb(self, kb_id: str | None, name: str, description: str = "") -> dict:
    with self._lock:
        data = self._load()
        kbs = data.setdefault("knowledge_bases", {})
        resolved_id = kb_id.strip() if kb_id else self._generate_kb_id_from_data(data, name)
        if resolved_id in kbs:
            raise ValueError(f"Knowledge base '{resolved_id}' already exists")
        now = utc_now_iso()
        entry = {
            "id": resolved_id,
            "name": name,
            "description": description,
            "paper_ids": [],
            "created_at": now,
            "updated_at": now,
        }
        kbs[resolved_id] = entry
        self._save(data)
        return entry
```

- [ ] **Step 5: Update membership timestamps**

Update `add_paper_to_kb()` and `remove_paper_from_kb()`:

```python
if paper_id not in kb["paper_ids"]:
    kb["paper_ids"].append(paper_id)
    kb["updated_at"] = utc_now_iso()
    self._save(data)
```

```python
before = list(kb["paper_ids"])
kb["paper_ids"] = [pid for pid in before if pid != paper_id]
if kb["paper_ids"] != before:
    kb["updated_at"] = utc_now_iso()
    self._save(data)
```

- [ ] **Step 6: Extend schemas and endpoint**

In `app/schemas.py`:

```python
class KBCreateRequest(BaseModel):
    kb_id: str | None = None
    name: str
    description: str = ""


class KBResponse(BaseModel):
    id: str
    name: str
    description: str = ""
    paper_ids: list[str] = []
    created_at: str | None = None
    updated_at: str | None = None
    paper_count: int | None = None
    indexed_count: int | None = None
    noted_count: int | None = None
```

In `app/main.py`, keep old compatibility:

```python
kb = _get_kb_manager().create_kb(req.kb_id, req.name, req.description)
```

- [ ] **Step 7: Add endpoint tests**

In `tests/test_kb_endpoints.py`, add:

```python
def test_create_kb_without_id_generates_id(client):
    response = client.post("/kb", json={"name": "Graph RAG", "description": "retrieval"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["id"] == "graph-rag"
    assert payload["name"] == "Graph RAG"
    assert payload["updated_at"]
```

- [ ] **Step 8: Verify and commit**

Run:

```powershell
& 'D:\Hcworkspace\Anoconda3\envs\research_agent\python.exe' -m pytest tests/test_kb_management.py tests/test_kb_endpoints.py -q
```

Commit:

```powershell
git add app/services/knowledge_base_manager.py app/schemas.py app/main.py tests/test_kb_management.py tests/test_kb_endpoints.py
git commit -m "feat: support research set creation contract"
```

---

### Task 2: Backend Derived Stats

**Files:**
- Modify: `app/main.py`
- Test: `tests/test_kb_endpoints.py`

- [ ] **Step 1: Add stats test**

Add an endpoint test that creates two papers in metadata, marks one indexed, creates one note, adds both to a KB, and expects:

```python
assert payload["paper_count"] == 2
assert payload["indexed_count"] == 1
assert payload["noted_count"] == 1
```

- [ ] **Step 2: Implement `_enrich_kb_response()`**

In `app/main.py`, add a helper near KB routes:

```python
def _enrich_kb_response(kb: dict) -> dict:
    paper_ids = list(kb.get("paper_ids", []))
    indexed_ids = {
        item.get("paper_id")
        for item in _get_vector_store().list_indexed_papers()
        if item.get("paper_id")
    }
    note_dir = _resolve_note_dir()
    noted_ids = {
        paper_id
        for paper_id in paper_ids
        if os.path.isfile(os.path.join(note_dir, f"{paper_id}_note.md"))
    }
    return {
        **kb,
        "paper_count": len(paper_ids),
        "indexed_count": sum(1 for paper_id in paper_ids if paper_id in indexed_ids),
        "noted_count": sum(1 for paper_id in paper_ids if paper_id in noted_ids),
    }
```

If `VectorStore` does not expose `list_indexed_papers()`, derive indexed IDs from the existing library index endpoint helper or Chroma metadata path used by `/library/index/status`.

- [ ] **Step 3: Apply enrichment consistently**

Use `_enrich_kb_response()` in:

```python
list_kbs
create_kb
add_paper_to_kb
remove_paper_from_kb
```

- [ ] **Step 4: Verify and commit**

Run:

```powershell
& 'D:\Hcworkspace\Anoconda3\envs\research_agent\python.exe' -m pytest tests/test_kb_endpoints.py -q
```

Commit:

```powershell
git add app/main.py tests/test_kb_endpoints.py
git commit -m "feat: enrich research set stats"
```

---

### Task 3: Frontend API Contract

**Files:**
- Modify: `frontend/src/api/types.ts`
- Modify: `frontend/src/api/knowledgeBase.ts`

- [ ] **Step 1: Update types**

In `frontend/src/api/types.ts`:

```ts
export interface KnowledgeBase {
  id: string;
  name: string;
  description: string;
  paper_ids: string[];
  created_at?: string | null;
  updated_at?: string | null;
  paper_count?: number | null;
  indexed_count?: number | null;
  noted_count?: number | null;
}

export interface KnowledgeBaseCreatePayload {
  kb_id?: string;
  name: string;
  description?: string;
}
```

- [ ] **Step 2: Update API helpers**

In `frontend/src/api/knowledgeBase.ts`:

```ts
import type { KnowledgeBase, KnowledgeBaseCreatePayload, KnowledgeBaseListResponse } from "./types";

export function createKnowledgeBase(payload: KnowledgeBaseCreatePayload) {
  return apiJson<KnowledgeBase>("/kb", { body: payload });
}

export async function addPapersToKnowledgeBase(kbId: string, paperIds: string[]) {
  let latest: KnowledgeBase | null = null;
  for (const paperId of paperIds) {
    latest = await addPaperToKnowledgeBase(kbId, paperId);
  }
  return latest;
}
```

- [ ] **Step 3: Verify TypeScript**

Run:

```powershell
cd frontend
npm test -- KnowledgeBasePage.test.tsx
```

Expected: current page tests may fail until Task 5 rewires UI, but TypeScript should show API shape issues early.

Commit:

```powershell
git add frontend/src/api/types.ts frontend/src/api/knowledgeBase.ts
git commit -m "feat: update research set frontend API contract"
```

---

### Task 4: Research Set Picker Utilities

**Files:**
- Create: `frontend/src/pages/knowledge-base/researchSetUtils.ts`
- Create: `frontend/src/pages/knowledge-base/ResearchSetPaperPicker.tsx`
- Modify: `frontend/src/pages/knowledge-base/KnowledgeBasePage.test.tsx`

- [ ] **Step 1: Create utilities**

Create `researchSetUtils.ts`:

```ts
import type { KnowledgeBase, PaperListItem } from "../../api/types";

export function getMemberPapers(papers: PaperListItem[], set: KnowledgeBase) {
  const byId = new Map(papers.map((paper) => [paper.paper_id, paper]));
  return set.paper_ids.map((paperId) => byId.get(paperId) ?? { paper_id: paperId, title: paperId, abstract: "" });
}

export function getAvailablePapers(papers: PaperListItem[], set: KnowledgeBase) {
  const memberIds = new Set(set.paper_ids);
  return papers.filter((paper) => !memberIds.has(paper.paper_id));
}

export function percent(count?: number | null, total?: number | null) {
  if (!count || !total) return 0;
  return Math.round((count / total) * 100);
}
```

- [ ] **Step 2: Create searchable picker**

Create `ResearchSetPaperPicker.tsx` with props:

```ts
interface ResearchSetPaperPickerProps {
  papers: PaperListItem[];
  selectedPaperIds: string[];
  onToggle: (paperId: string) => void;
}
```

Behavior:
- Search input filters by title or paper ID.
- Each row uses a checkbox.
- Only title and ID are shown; no abstract.
- Empty state says no matching papers.

- [ ] **Step 3: Add failing UI test**

In `KnowledgeBasePage.test.tsx`, add a test that searches `RAG`, selects `RAG Systems`, clicks add, and expects `addPapersToKnowledgeBase("kb_cv", ["paper_002"])`.

- [ ] **Step 4: Verify failure and commit utilities**

Run:

```powershell
cd frontend
npm test -- KnowledgeBasePage.test.tsx
```

Expected: utility import passes; page integration test fails until Task 5.

Commit:

```powershell
git add frontend/src/pages/knowledge-base/researchSetUtils.ts frontend/src/pages/knowledge-base/ResearchSetPaperPicker.tsx frontend/src/pages/knowledge-base/KnowledgeBasePage.test.tsx
git commit -m "feat: add research set paper picker"
```

---

### Task 5: Productize KnowledgeBasePage

**Files:**
- Modify: `frontend/src/pages/knowledge-base/KnowledgeBasePage.tsx`
- Modify: `frontend/src/pages/knowledge-base/KnowledgeBasePage.test.tsx`

- [ ] **Step 1: Replace create form**

Remove `kbId` state from normal UI. Keep only:

```ts
const [name, setName] = useState("");
const [description, setDescription] = useState("");
const [selectedPaperIds, setSelectedPaperIds] = useState<Record<string, string[]>>({});
```

Submit:

```ts
createMutation.mutate({ name: name.trim(), description: description.trim() });
```

- [ ] **Step 2: Replace page copy**

Use:
- Heading: `Research Sets`
- Description: `Group papers into reusable sets for QA, comparison, and workflow runs.`
- Empty state title: `No research sets`
- Action button: `Create Set`

- [ ] **Step 3: Replace single select with multi-select picker**

For each set:

```tsx
<ResearchSetPaperPicker
  papers={getAvailablePapers(papers, kb)}
  selectedPaperIds={selectedPaperIds[kb.id] ?? []}
  onToggle={(paperId) => toggleSelectedPaper(kb.id, paperId)}
/>
```

Add button calls:

```ts
addMutation.mutate({ targetKbId: kb.id, paperIds: selectedPaperIds[kb.id] ?? [] });
```

- [ ] **Step 4: Show member titles and stats**

Use `getMemberPapers(papers, kb)` and display:
- title as primary text
- paper ID as muted secondary text
- `paper_count`, `indexed_count`, `noted_count`
- indexed percentage with light-green progress bar

- [ ] **Step 5: Add action links**

Per set, show compact buttons:
- `Ask` -> `/qa?scope=kb&kb_id=${kb.id}`
- `Compare` -> `/compare?kb_id=${kb.id}`
- `Workflow` -> `/workflow/new?kb_id=${kb.id}`

- [ ] **Step 6: Verify frontend test**

Run:

```powershell
cd frontend
npm test -- KnowledgeBasePage.test.tsx
```

Expected: all KnowledgeBasePage tests pass.

Commit:

```powershell
git add frontend/src/pages/knowledge-base/KnowledgeBasePage.tsx frontend/src/pages/knowledge-base/KnowledgeBasePage.test.tsx
git commit -m "feat: productize research sets page"
```

---

### Task 6: Navigation and Handoff

**Files:**
- Modify: `frontend/src/components/layout/navItems.ts`
- Optionally modify: `frontend/src/pages/qa/QaPage.tsx`
- Optionally modify: `frontend/src/pages/compare/ComparePage.tsx`
- Optionally modify: `frontend/src/pages/workflow/NewRunPage.tsx`

- [ ] **Step 1: Rename sidebar**

In `navItems.ts`:

```ts
{ label: "Research Sets", path: "/knowledge-base", icon: Library }
```

- [ ] **Step 2: Verify downstream pages tolerate query params**

Open QA, Compare, and Workflow pages. If they ignore unknown query params safely, keep this task to navigation only. If a page breaks, add minimal parsing and fallback.

- [ ] **Step 3: Verify and commit**

Run:

```powershell
cd frontend
npm test -- KnowledgeBasePage.test.tsx
```

Commit:

```powershell
git add frontend/src/components/layout/navItems.ts frontend/src/pages/qa/QaPage.tsx frontend/src/pages/compare/ComparePage.tsx frontend/src/pages/workflow/NewRunPage.tsx
git commit -m "feat: rename knowledge base navigation"
```

---

### Task 7: Final Verification

**Files:**
- No product files unless verification reveals a bug.

- [ ] **Step 1: Run backend tests**

```powershell
& 'D:\Hcworkspace\Anoconda3\envs\research_agent\python.exe' -m pytest tests/test_kb_management.py tests/test_kb_endpoints.py -q
```

- [ ] **Step 2: Run frontend tests**

```powershell
cd frontend
npm test -- KnowledgeBasePage.test.tsx
```

- [ ] **Step 3: Run TypeScript build check if available**

```powershell
cd frontend
npm run build
```

- [ ] **Step 4: Inspect final diff**

```powershell
git status --short
git log --oneline -8
```

- [ ] **Step 5: Final handoff**

Report:
- backend contract changes
- frontend UX changes
- tests run
- remaining known limitations, especially that downstream pages may receive `kb_id` links before they fully consume them

---

## Self-Review

- Spec coverage: auto ID, stats, searchable picker, page rename, member titles, downstream actions, and tests are covered.
- Placeholder scan: no TBD or undefined "implement later" steps.
- Type consistency: backend remains `KBResponse`; frontend keeps `KnowledgeBase` while UI presents "Research Sets".
