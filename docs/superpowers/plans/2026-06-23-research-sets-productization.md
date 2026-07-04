# Research Sets Productization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn the current Knowledge Base page into a productized Research Sets experience for grouping papers and reusing those sets in QA, Compare, and Workflow entry points.

**Architecture:** Keep the existing backend `/kb` storage and manager as the compatibility layer, but expose a friendlier Research Set API contract and UI language. Implement the first usable slice as a single-page productized manager with auto-generated IDs, searchable multi-select paper assignment, richer set statistics, and clear downstream action links. Defer deep data-model migrations until the UI proves useful.

**Tech Stack:** FastAPI + Pydantic backend, JSON-backed `KnowledgeBaseManager`, React + TypeScript + TanStack Query frontend, Vitest + Testing Library tests, Tailwind CSS styling.

---

## File Structure

- Modify `app/services/knowledge_base_manager.py`
  - Add slug generation, `updated_at`, and idempotent paper membership helpers.
  - Preserve the existing JSON registry format and tolerate old records.
- Modify `app/schemas.py`
  - Make `kb_id` optional for creation.
  - Add `updated_at` and optional UI-friendly stats fields to `KBResponse`.
- Modify `app/main.py`
  - Keep `/kb` endpoints.
  - Add backend-generated IDs when `kb_id` is omitted.
  - Enrich list responses with paper/note/index stats.
- Modify `frontend/src/api/types.ts`
  - Extend `KnowledgeBase`.
  - Add `KnowledgeBaseCreatePayload`.
- Modify `frontend/src/api/knowledgeBase.ts`
  - Stop requiring `kb_id`.
  - Add batch add helper.
- Create `frontend/src/pages/knowledge-base/researchSetUtils.ts`
  - Local UI utilities for derived paper lookups, stats, filtering, and slug-independent display.
- Create `frontend/src/pages/knowledge-base/ResearchSetPaperPicker.tsx`
  - Searchable, multi-select paper picker for adding papers.
- Modify `frontend/src/pages/knowledge-base/KnowledgeBasePage.tsx`
  - Rename UI copy to Research Sets.
  - Replace KB ID form with Name/Description.
  - Show cards with stats and clear actions.
  - Show member paper titles instead of raw IDs.
- Modify `frontend/src/pages/knowledge-base/KnowledgeBasePage.test.tsx`
  - Update tests for auto ID creation, search multi-select, stats, and member removal.
- Modify `frontend/src/components/layout/navItems.ts`
  - Rename sidebar item from Knowledge Base to Research Sets.
- Optional follow-up after first pass: update `docs/KB_MANAGEMENT.md` with user-facing Research Sets wording.

---

### Task 1: Backend Research Set Creation Contract

**Files:**
- Modify: `app/services/knowledge_base_manager.py`
- Modify: `app/schemas.py`
- Modify: `app/main.py`

- [ ] **Step 1: Add manager tests manually through a focused Python snippet**

Run this before changes to understand current behavior:

```powershell
& 'D:\Hcworkspace\Anoconda3\envs\research_agent\python.exe' - <<'PY'
from pathlib import Path
from tempfile import TemporaryDirectory
from app.services.knowledge_base_manager import KnowledgeBaseManager

with TemporaryDirectory() as tmp:
    manager = KnowledgeBaseManager(Path(tmp) / "knowledge_bases.json")
    print(manager.create_kb("my_set", "My Set", "Demo"))
    print(manager.list_kbs())
PY
```

Expected now: creation requires the caller to provide `my_set`.

- [ ] **Step 2: Add slug and timestamp helpers**

In `app/services/knowledge_base_manager.py`, add imports and helpers near the constants:

```python
import re

def _slugify_name(name: str) -> str:
    value = re.sub(r"[^a-zA-Z0-9\u4e00-\u9fff]+", "-", name.strip().lower()).strip("-")
    return value or "research-set"

def _normalize_entry(entry: dict) -> dict:
    entry.setdefault("description", "")
    entry.setdefault("paper_ids", [])
    entry.setdefault("created_at", utc_now_iso())
    entry.setdefault("updated_at", entry.get("created_at") or utc_now_iso())
    return entry
```

- [ ] **Step 3: Make default KB readable and normalized**

Replace the default entry in `_load()` with:

```python
DEFAULT_KB: {
    "id": DEFAULT_KB,
    "name": "Default Research Set",
    "description": "Papers not yet organized into a focused research set.",
    "paper_ids": [],
    "created_at": utc_now_iso(),
    "updated_at": utc_now_iso(),
}
```

After loading JSON successfully, normalize entries before returning:

```python
data = json.loads(self._path.read_text(encoding="utf-8"))
kbs = data.setdefault("knowledge_bases", {})
for entry in kbs.values():
    _normalize_entry(entry)
return data
```

- [ ] **Step 4: Let manager generate unique IDs**

Add this method to `KnowledgeBaseManager`:

```python
def generate_kb_id(self, name: str) -> str:
    data = self._load()
    existing = set(data.get("knowledge_bases", {}))
    base = _slugify_name(name)
    candidate = base
    index = 2
    while candidate in existing:
        candidate = f"{base}-{index}"
        index += 1
    return candidate
```

Update `create_kb` signature and body:

```python
def create_kb(self, kb_id: str | None, name: str, description: str = "") -> dict:
    with self._lock:
        data = self._load()
        kbs = data.setdefault("knowledge_bases", {})
        resolved_id = kb_id.strip() if kb_id else self.generate_kb_id(name)
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

In `add_paper_to_kb`, set `updated_at` when a paper is added:

```python
if paper_id not in kb["paper_ids"]:
    kb["paper_ids"].append(paper_id)
    kb["updated_at"] = utc_now_iso()
    self._save(data)
```

In `remove_paper_from_kb`, only save when membership changes:

```python
before = list(kb["paper_ids"])
kb["paper_ids"] = [pid for pid in before if pid != paper_id]
if kb["paper_ids"] != before:
    kb["updated_at"] = utc_now_iso()
    self._save(data)
```

- [ ] **Step 6: Relax create schema**

In `app/schemas.py`, change `KBCreateRequest`:

```python
class KBCreateRequest(BaseModel):
    kb_id: str | None = None
    name: str
    description: str = ""
```

Extend `KBResponse`:

```python
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

- [ ] **Step 7: Generate IDs in the endpoint**

In `app/main.py`, keep the route but pass optional ID:

```python
kb = _get_kb_manager().create_kb(req.kb_id, req.name, req.description)
```

Expected behavior: old clients can still send `kb_id`; new UI can omit it.

- [ ] **Step 8: Run backend sanity check**

Run:

```powershell
& 'D:\Hcworkspace\Anoconda3\envs\research_agent\python.exe' -m py_compile app\services\knowledge_base_manager.py app\schemas.py app\main.py
```

Expected: no output and exit code `0`.

- [ ] **Step 9: Commit backend contract**

```powershell
git add app/services/knowledge_base_manager.py app/schemas.py app/main.py
git commit -m "feat: productize research set creation"
```

---

### Task 2: Enriched Research Set Stats

**Files:**
- Modify: `app/main.py`
- Modify: `frontend/src/api/types.ts`

- [ ] **Step 1: Add stat enrichment helper**

In `app/main.py`, add a private helper near the KB endpoints:

```python
def _enrich_kb_response(kb: dict) -> KBResponse:
    paper_ids = kb.get("paper_ids", [])
    indexed_count = 0
    noted_count = 0
    for paper_id in paper_ids:
        if _is_paper_indexed(paper_id):
            indexed_count += 1
        note_path = Path(settings.note_dir) / f"{paper_id}_note.md"
        if note_path.is_file():
            noted_count += 1
    payload = {
        **kb,
        "paper_count": len(paper_ids),
        "indexed_count": indexed_count,
        "noted_count": noted_count,
    }
    return KBResponse(**payload)
```

- [ ] **Step 2: Use enriched responses**

Update list endpoint:

```python
return KBListResponse(
    count=len(items),
    knowledge_bases=[_enrich_kb_response(kb) for kb in items],
)
```

Update create/add/remove endpoints to return:

```python
return _enrich_kb_response(kb)
```

- [ ] **Step 3: Extend frontend type**

In `frontend/src/api/types.ts`, extend `KnowledgeBase`:

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
```

- [ ] **Step 4: Run backend and type-adjacent tests**

Run:

```powershell
& 'D:\Hcworkspace\Anoconda3\envs\research_agent\python.exe' -m py_compile app\main.py app\schemas.py
cd frontend
npm test -- KnowledgeBasePage.test.tsx
```

Expected: Python compile passes; frontend tests may fail because UI still expects old labels. That is acceptable before Task 4.

- [ ] **Step 5: Commit stats contract**

```powershell
git add app/main.py app/schemas.py frontend/src/api/types.ts
git commit -m "feat: expose research set stats"
```

---

### Task 3: Frontend API Contract Cleanup

**Files:**
- Modify: `frontend/src/api/knowledgeBase.ts`
- Modify: `frontend/src/api/types.ts`

- [ ] **Step 1: Add create payload type**

In `frontend/src/api/types.ts`, add:

```ts
export interface KnowledgeBaseCreatePayload {
  name: string;
  description?: string;
  kb_id?: string | null;
}
```

- [ ] **Step 2: Use payload type in API**

In `frontend/src/api/knowledgeBase.ts`, update imports:

```ts
import type { KnowledgeBase, KnowledgeBaseCreatePayload, KnowledgeBaseListResponse } from "./types";
```

Update create function:

```ts
export function createKnowledgeBase(payload: KnowledgeBaseCreatePayload) {
  return apiJson<KnowledgeBase>("/kb", { body: payload });
}
```

Add batch helper:

```ts
export async function addPapersToKnowledgeBase(kbId: string, paperIds: string[]) {
  let latest: KnowledgeBase | null = null;
  for (const paperId of paperIds) {
    latest = await addPaperToKnowledgeBase(kbId, paperId);
  }
  return latest;
}
```

- [ ] **Step 3: Run API type test**

Run:

```powershell
cd frontend
npm test -- KnowledgeBasePage.test.tsx
```

Expected before UI update: old tests may fail on payload expectations. No TypeScript import runtime failure should occur.

- [ ] **Step 4: Commit API cleanup**

```powershell
git add frontend/src/api/knowledgeBase.ts frontend/src/api/types.ts
git commit -m "feat: simplify research set api payloads"
```

---

### Task 4: Research Set UI Utilities and Picker

**Files:**
- Create: `frontend/src/pages/knowledge-base/researchSetUtils.ts`
- Create: `frontend/src/pages/knowledge-base/ResearchSetPaperPicker.tsx`
- Modify: `frontend/src/pages/knowledge-base/KnowledgeBasePage.test.tsx`

- [ ] **Step 1: Create utility functions**

Create `frontend/src/pages/knowledge-base/researchSetUtils.ts`:

```ts
import type { KnowledgeBase, PaperListItem } from "../../api/types";

export function getPaperTitle(papers: PaperListItem[], paperId: string) {
  return papers.find((paper) => paper.paper_id === paperId)?.title || paperId;
}

export function getAvailablePapers(papers: PaperListItem[], set: KnowledgeBase) {
  const assigned = new Set(set.paper_ids);
  return papers.filter((paper) => !assigned.has(paper.paper_id));
}

export function filterPapers(papers: PaperListItem[], query: string) {
  const normalized = query.trim().toLowerCase();
  if (!normalized) return papers;
  return papers.filter((paper) => {
    const haystack = `${paper.paper_id} ${paper.title ?? ""} ${paper.abstract ?? ""}`.toLowerCase();
    return haystack.includes(normalized);
  });
}

export function formatCoverage(count: number | null | undefined, total: number) {
  if (!total) return "0%";
  return `${Math.round(((count ?? 0) / total) * 100)}%`;
}
```

- [ ] **Step 2: Create searchable multi-select picker**

Create `frontend/src/pages/knowledge-base/ResearchSetPaperPicker.tsx`:

```tsx
import { Search } from "lucide-react";
import { useMemo, useState } from "react";
import type { PaperListItem } from "../../api/types";
import { filterPapers } from "./researchSetUtils";

interface ResearchSetPaperPickerProps {
  papers: PaperListItem[];
  selectedPaperIds: string[];
  onToggle: (paperId: string) => void;
}

export function ResearchSetPaperPicker({ papers, selectedPaperIds, onToggle }: ResearchSetPaperPickerProps) {
  const [query, setQuery] = useState("");
  const selected = new Set(selectedPaperIds);
  const visiblePapers = useMemo(() => filterPapers(papers, query).slice(0, 8), [papers, query]);

  return (
    <div className="rounded-md border border-line bg-surface p-3">
      <label className="relative block">
        <Search className="pointer-events-none absolute left-3 top-2.5 h-4 w-4 text-muted" aria-hidden="true" />
        <input
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          placeholder="Search papers by title, abstract, or ID"
          className="w-full rounded-md border border-line bg-panel py-2 pl-9 pr-3 text-sm text-ink"
        />
      </label>
      <div className="mt-3 max-h-64 space-y-2 overflow-auto">
        {visiblePapers.length === 0 ? (
          <p className="text-sm text-muted">No matching papers available.</p>
        ) : (
          visiblePapers.map((paper) => (
            <label key={paper.paper_id} className="flex cursor-pointer items-start gap-3 rounded-md border border-line bg-panel px-3 py-2 hover:bg-white">
              <input
                type="checkbox"
                checked={selected.has(paper.paper_id)}
                onChange={() => onToggle(paper.paper_id)}
                className="mt-1"
              />
              <span className="min-w-0">
                <span className="block truncate text-sm font-medium text-ink">{paper.title || paper.paper_id}</span>
                <span className="block truncate text-xs text-muted">{paper.paper_id}</span>
              </span>
            </label>
          ))
        )}
      </div>
    </div>
  );
}
```

- [ ] **Step 3: Add tests for picker behavior through page test**

In `frontend/src/pages/knowledge-base/KnowledgeBasePage.test.tsx`, prepare to test:

```ts
it("adds multiple searched papers to a research set", async () => {
  const user = userEvent.setup();
  renderPage();

  await screen.findByText("Computer Vision");
  await user.type(screen.getByPlaceholderText(/search papers/i), "RAG");
  await user.click(screen.getByRole("checkbox", { name: /RAG Systems paper_002/i }));
  await user.click(screen.getByRole("button", { name: /add selected/i }));

  expect(vi.mocked(kbApi.addPaperToKnowledgeBase).mock.calls[0][0]).toBe("kb_cv");
  expect(vi.mocked(kbApi.addPaperToKnowledgeBase).mock.calls[0][1]).toBe("paper_002");
});
```

This test will fail until Task 5 wires the picker into the page.

- [ ] **Step 4: Commit picker scaffolding**

```powershell
git add frontend/src/pages/knowledge-base/researchSetUtils.ts frontend/src/pages/knowledge-base/ResearchSetPaperPicker.tsx frontend/src/pages/knowledge-base/KnowledgeBasePage.test.tsx
git commit -m "feat: add research set paper picker"
```

---

### Task 5: Productize KnowledgeBasePage as Research Sets

**Files:**
- Modify: `frontend/src/pages/knowledge-base/KnowledgeBasePage.tsx`
- Modify: `frontend/src/pages/knowledge-base/KnowledgeBasePage.test.tsx`
- Modify: `frontend/src/components/layout/navItems.ts`

- [ ] **Step 1: Update imports and state**

In `KnowledgeBasePage.tsx`, replace the `PaperSelector` import with:

```ts
import { BookOpen, GitCompare, MessageSquare, PlayCircle, Plus, X } from "lucide-react";
import { Link } from "react-router-dom";
import { ResearchSetPaperPicker } from "./ResearchSetPaperPicker";
import { formatCoverage, getAvailablePapers, getPaperTitle } from "./researchSetUtils";
```

Remove `kbId` state. Add:

```ts
const [selectedPapers, setSelectedPapers] = useState<Record<string, string[]>>({});
```

- [ ] **Step 2: Create without manual ID**

Update `handleCreate`:

```ts
const handleCreate = (event: FormEvent) => {
  event.preventDefault();
  if (!name.trim()) return;
  createMutation.mutate({ name: name.trim(), description: description.trim() });
};
```

In `onSuccess`, remove `setKbId("")`.

- [ ] **Step 3: Update hero copy and form**

Replace title and description:

```tsx
<h1 className="text-2xl font-semibold text-ink">Research Sets</h1>
<p className="mt-2 max-w-3xl text-sm leading-6 text-muted">
  Build focused paper collections for scoped QA, comparison, notes, and workflow analysis.
</p>
```

Replace the form grid with:

```tsx
<form onSubmit={handleCreate} className="grid gap-3 rounded-md border border-line bg-panel p-4 shadow-panel lg:grid-cols-[1fr_1.4fr_auto] lg:items-end">
  <label className="block">
    <span className="text-xs font-medium uppercase text-muted">Name</span>
    <input value={name} onChange={(event) => setName(event.target.value)} placeholder="e.g. Infrared Small Target Detection" className="mt-1 w-full rounded-md border border-line px-3 py-2 text-sm" />
  </label>
  <label className="block">
    <span className="text-xs font-medium uppercase text-muted">Description</span>
    <input value={description} onChange={(event) => setDescription(event.target.value)} placeholder="What research question does this set support?" className="mt-1 w-full rounded-md border border-line px-3 py-2 text-sm" />
  </label>
  <button type="submit" disabled={!name.trim() || createMutation.isPending} className="inline-flex items-center justify-center gap-2 rounded-md bg-accent px-4 py-2 text-sm font-medium text-white hover:bg-accent-hover disabled:opacity-60">
    <Plus className="h-4 w-4" aria-hidden="true" />
    Create set
  </button>
</form>
```

- [ ] **Step 4: Replace cards with productized set cards**

Inside `knowledgeBases.map`, compute:

```tsx
const assignedPapers = kb.paper_ids.map((paperId) => ({ paperId, title: getPaperTitle(papers, paperId) }));
const availablePapers = getAvailablePapers(papers, kb);
const selectedForSet = selectedPapers[kb.id] ?? [];
```

Use this card header:

```tsx
<div className="flex flex-wrap items-start justify-between gap-4">
  <div className="min-w-0">
    <h2 className="text-base font-semibold text-ink">{kb.name}</h2>
    <p className="mt-1 text-xs text-muted">Set ID: {kb.id}</p>
    {kb.description && <p className="mt-2 text-sm leading-6 text-muted">{kb.description}</p>}
  </div>
  <span className="rounded-full bg-green-50 px-3 py-1 text-xs font-medium text-green-700">{kb.paper_count ?? kb.paper_ids.length} papers</span>
</div>
```

Add stat row:

```tsx
<div className="mt-4 grid gap-2 sm:grid-cols-3">
  <div className="rounded-md bg-surface p-3">
    <p className="text-xs uppercase text-muted">Indexed</p>
    <p className="mt-1 text-lg font-semibold text-ink">{formatCoverage(kb.indexed_count, kb.paper_ids.length)}</p>
  </div>
  <div className="rounded-md bg-surface p-3">
    <p className="text-xs uppercase text-muted">Notes</p>
    <p className="mt-1 text-lg font-semibold text-ink">{formatCoverage(kb.noted_count, kb.paper_ids.length)}</p>
  </div>
  <div className="rounded-md bg-surface p-3">
    <p className="text-xs uppercase text-muted">Updated</p>
    <p className="mt-1 truncate text-sm font-medium text-ink">{kb.updated_at ? new Date(kb.updated_at).toLocaleDateString() : "—"}</p>
  </div>
</div>
```

Add action links:

```tsx
<div className="mt-4 flex flex-wrap gap-2">
  <Link to={`/qa?scope=kb:${encodeURIComponent(kb.id)}`} className="inline-flex items-center gap-2 rounded-md border border-line px-3 py-2 text-sm font-medium text-muted hover:bg-surface">
    <MessageSquare className="h-4 w-4" /> Ask
  </Link>
  <Link to={`/compare?kb=${encodeURIComponent(kb.id)}`} className="inline-flex items-center gap-2 rounded-md border border-line px-3 py-2 text-sm font-medium text-muted hover:bg-surface">
    <GitCompare className="h-4 w-4" /> Compare
  </Link>
  <Link to={`/workflow/new?kb=${encodeURIComponent(kb.id)}`} className="inline-flex items-center gap-2 rounded-md border border-line px-3 py-2 text-sm font-medium text-muted hover:bg-surface">
    <PlayCircle className="h-4 w-4" /> Run workflow
  </Link>
  <Link to="/papers" className="inline-flex items-center gap-2 rounded-md border border-line px-3 py-2 text-sm font-medium text-muted hover:bg-surface">
    <BookOpen className="h-4 w-4" /> Browse papers
  </Link>
</div>
```

- [ ] **Step 5: Wire multi-select add**

Render picker:

```tsx
<div className="mt-4">
  <ResearchSetPaperPicker
    papers={availablePapers}
    selectedPaperIds={selectedForSet}
    onToggle={(paperId) =>
      setSelectedPapers((current) => {
        const existing = current[kb.id] ?? [];
        const next = existing.includes(paperId)
          ? existing.filter((id) => id !== paperId)
          : [...existing, paperId];
        return { ...current, [kb.id]: next };
      })
    }
  />
  <button
    type="button"
    disabled={selectedForSet.length === 0 || addMutation.isPending}
    onClick={() => {
      selectedForSet.forEach((paperId) => addMutation.mutate({ targetKbId: kb.id, paperId }));
      setSelectedPapers((current) => ({ ...current, [kb.id]: [] }));
    }}
    className="mt-3 rounded-md bg-accent px-3 py-2 text-sm font-medium text-white hover:bg-accent-hover disabled:opacity-60"
  >
    Add selected
  </button>
</div>
```

- [ ] **Step 6: Show member titles**

Replace raw paper ID rows:

```tsx
{assignedPapers.length === 0 ? (
  <EmptyState title="No papers in this set" description="Search and add papers to make this set useful for scoped QA and workflows." />
) : (
  assignedPapers.map((paper) => (
    <div key={paper.paperId} className="flex items-center justify-between gap-3 rounded-md border border-line bg-surface px-3 py-2">
      <div className="min-w-0">
        <p className="truncate text-sm font-medium text-ink">{paper.title}</p>
        <p className="truncate text-xs text-muted">{paper.paperId}</p>
      </div>
      <button type="button" onClick={() => removeMutation.mutate({ targetKbId: kb.id, paperId: paper.paperId })} className="inline-flex h-7 w-7 items-center justify-center rounded border border-line text-muted hover:border-red-200 hover:bg-red-50 hover:text-red-600" aria-label={`Remove ${paper.title} from ${kb.name}`}>
        <X className="h-4 w-4" aria-hidden="true" />
      </button>
    </div>
  ))
)}
```

- [ ] **Step 7: Rename nav label**

In `frontend/src/components/layout/navItems.ts`, change:

```ts
{ label: "Research Sets", path: "/knowledge-base", icon: Library },
```

- [ ] **Step 8: Update tests**

Change create test:

```ts
it("creates a research set without manual ID", async () => {
  const user = userEvent.setup();
  renderPage();

  await user.type(await screen.findByLabelText(/^name$/i), "NLP");
  await user.click(screen.getByRole("button", { name: /create set/i }));

  expect(vi.mocked(kbApi.createKnowledgeBase).mock.calls[0][0]).toEqual({ name: "NLP", description: "" });
});
```

Change remove expectation:

```ts
await user.click(screen.getByLabelText("Remove Attention Survey from Computer Vision"));
```

- [ ] **Step 9: Run frontend tests**

Run:

```powershell
cd frontend
npm test -- KnowledgeBasePage.test.tsx
```

Expected: all KnowledgeBasePage tests pass.

- [ ] **Step 10: Commit UI productization**

```powershell
git add frontend/src/pages/knowledge-base frontend/src/components/layout/navItems.ts
git commit -m "feat: productize research sets page"
```

---

### Task 6: Scope Handoff to QA, Compare, and Workflow

**Files:**
- Modify: `frontend/src/pages/qa/QaPage.tsx`
- Modify: `frontend/src/pages/compare/ComparePage.tsx`
- Modify: `frontend/src/pages/workflow/WorkflowPage.tsx`

- [ ] **Step 1: Make links non-breaking**

Confirm each target page ignores unknown query params today. If the page does not parse query params, no backend change is required for this task.

- [ ] **Step 2: Add visible scope notice in QA**

In `QaPage.tsx`, import:

```ts
import { useSearchParams } from "react-router-dom";
```

Inside the component:

```ts
const [searchParams] = useSearchParams();
const kbScope = searchParams.get("scope")?.startsWith("kb:") ? searchParams.get("scope")?.slice(3) : null;
```

Render near the chat header:

```tsx
{kbScope && (
  <div className="rounded-md border border-line bg-green-50 px-3 py-2 text-sm text-green-700">
    Asking within research set: {kbScope}
  </div>
)}
```

Do not change backend QA retrieval in this task; this is only a handoff affordance.

- [ ] **Step 3: Add comparable notices to Compare and Workflow**

In `ComparePage.tsx`, parse `kb` query param and render:

```tsx
{kbId && <p className="rounded-md border border-line bg-green-50 px-3 py-2 text-sm text-green-700">Comparing papers from research set: {kbId}</p>}
```

In `WorkflowPage.tsx`, parse `kb` query param and render:

```tsx
{kbId && <p className="rounded-md border border-line bg-green-50 px-3 py-2 text-sm text-green-700">Workflow will start from research set: {kbId}</p>}
```

- [ ] **Step 4: Run targeted tests**

Run:

```powershell
cd frontend
npm test -- QaPage.test.tsx ComparePage.test.tsx
```

Expected: existing tests pass. Add tests for notices only if current test harness already wraps these pages in a router.

- [ ] **Step 5: Commit scope handoff**

```powershell
git add frontend/src/pages/qa/QaPage.tsx frontend/src/pages/compare/ComparePage.tsx frontend/src/pages/workflow/WorkflowPage.tsx
git commit -m "feat: link research sets into workflows"
```

---

### Task 7: Final Verification and Cleanup

**Files:**
- No new source files expected.
- Optional docs: `docs/KB_MANAGEMENT.md`

- [ ] **Step 1: Run focused frontend tests**

```powershell
cd frontend
npm test -- KnowledgeBasePage.test.tsx QaPage.test.tsx ComparePage.test.tsx
```

Expected: all tests pass.

- [ ] **Step 2: Run backend syntax check**

```powershell
& 'D:\Hcworkspace\Anoconda3\envs\research_agent\python.exe' -m py_compile app\services\knowledge_base_manager.py app\schemas.py app\main.py
```

Expected: exit code `0`.

- [ ] **Step 3: Check staged diff hygiene**

```powershell
git diff --check
git status --short --branch
```

Expected:
- `git diff --check` has no output.
- Only intended source files are modified.
- Runtime files such as `app/storage/memory.db-shm` and `app/storage/memory.db-wal` remain untracked and are not staged.

- [ ] **Step 4: Manual browser smoke test**

With the app running at `http://127.0.0.1:5173`:

1. Open `/knowledge-base`.
2. Confirm sidebar label says `Research Sets`.
3. Create a set named `Infrared Small Target Detection`.
4. Search for one paper by title.
5. Select it and click `Add selected`.
6. Confirm the card paper count increments.
7. Confirm member list shows title and paper ID.
8. Click `Ask`; confirm QA opens and shows the research-set notice.
9. Return to Research Sets and remove the paper.

- [ ] **Step 5: Final commit if docs changed**

```powershell
git add docs/KB_MANAGEMENT.md
git commit -m "docs: describe research sets workflow"
```

---

## Self-Review

**Spec coverage:** The plan covers renaming the user-facing feature, removing manual KB ID input, auto-generating IDs, searchable multi-select paper assignment, richer cards, stats, member titles, empty states, and downstream action links to QA/Compare/Workflow.

**Placeholder scan:** No task contains TBD, TODO, or unspecified error handling. Each code-changing step identifies concrete files and code snippets.

**Type consistency:** The backend keeps `KBResponse` and `/kb` for compatibility while frontend introduces `KnowledgeBaseCreatePayload`. `updated_at`, `paper_count`, `indexed_count`, and `noted_count` are consistently optional across backend and frontend to tolerate old registry data.
