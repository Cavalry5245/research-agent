# Zotero Collection Processing Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build Milestone 2: make a ResearchRun process a Zotero collection into local parsed/indexed papers and per-paper Knowledge Pack notes with item-level status tracking.

**Architecture:** Extend the Milestone 1 workflow package with item-level run schemas, a Zotero collection intake adapter, a local paper-processing service, and run orchestration that updates the existing file-backed store and Knowledge Pack artifacts. Keep external MCP, Semantic Scholar, arXiv, and Obsidian publishing out of this milestone; use fake clients in tests and local Zotero HTTP/PDF resolution as the real integration path.

**Tech Stack:** Python 3.11, Pydantic, FastAPI, Streamlit, PyMuPDF, local JSON vector store, pytest, `httpx` for Zotero local API calls, file-backed run persistence.

---

## Scope

This plan implements only Milestone 2 from:

- `docs/superpowers/specs/2026-06-09-research-agent-m2-m4-roadmap-design.md`

Included:

- Item-level paper status models on `ResearchRun`.
- Collection intake models and service.
- Zotero local API client and PDF path resolver.
- Local per-paper processing coordinator.
- Knowledge Pack updates for paper notes, summary counts, trace, and tool-call records.
- `POST /research-runs/{run_id}/execute-local` API endpoint.
- Streamlit workflow page action and item-status monitor.
- Focused tests with fake Zotero, fake parser, fake embedder, fake vector store, and fake note generator.

Excluded:

- ResearchAgent MCP Server.
- Semantic Scholar and arXiv enrichment.
- Obsidian MCP publishing.
- Multi-agent literature synthesis.
- Final screen recording.
- `.env` edits. Do not modify `.env` without explicit user approval.

## File Structure

- Modify: `app/research_workflow/schemas.py`
  - Add paper-item lifecycle models and execution result fields.
- Create: `app/research_workflow/zotero_intake.py`
  - Define `ZoteroCollectionClient`, normalized intake models, local HTTP client, PDF resolver, and `CollectionIntakeService`.
- Create: `app/research_workflow/paper_processing.py`
  - Define `PaperProcessingService`, dependency protocols, safe PDF copy, parse/save/index/note workflow, and item result model.
- Modify: `app/research_workflow/knowledge_pack.py`
  - Add deterministic summary rewrite, trace rewrite, paper-note writing, and tool-call append helpers.
- Modify: `app/research_workflow/service.py`
  - Add `execute_local_run()` orchestration and item status updates.
- Modify: `app/routers/research_runs.py`
  - Add `POST /research-runs/{run_id}/execute-local`.
- Modify: `ui/streamlit_app.py`
  - Add "Process Local Collection" button and item-status display.
- Test: `tests/test_research_run_service.py`
  - Add schema, orchestration, Knowledge Pack, and failure tests.
- Test: `tests/test_zotero_intake.py`
  - Add Zotero intake normalization and PDF resolution tests.
- Test: `tests/test_paper_processing_service.py`
  - Add single-paper processing tests.
- Test: `tests/test_research_run_router.py`
  - Add API execution endpoint test.
- Test: `tests/test_research_workflow_ui_import.py`
  - Add UI source smoke checks.

## Shared Test Helpers

Use the reliable interpreter for all verification commands:

```powershell
& 'D:\Hcworkspace\Anoconda3\envs\research_agent\python.exe' -m pytest <paths> -q
```

When a task writes tests that use fake PDFs, use plain bytes instead of real PDF parsing unless the test specifically needs PyMuPDF. The processing-service tests should inject fake parser functions so they do not need a valid PDF.

## Data Model

Add these exact models and field names in `app/research_workflow/schemas.py`.

```python
from typing import Any, Literal


ResearchRunPaperStatus = Literal["queued", "running", "completed", "failed", "skipped"]


class ResearchRunPaperArtifact(BaseModel):
    label: str
    path: str
    kind: Literal["pdf", "markdown", "json", "vector_index"]


class ResearchRunPaperItem(BaseModel):
    item_id: str
    title: str
    zotero_item_id: str
    paper_id: str | None = None
    pdf_path: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    status: ResearchRunPaperStatus = "queued"
    progress: float = Field(default=0.0, ge=0.0, le=1.0)
    error: str | None = None
    artifacts: list[ResearchRunPaperArtifact] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime
    started_at: datetime | None = None
    completed_at: datetime | None = None
```

Update `ResearchRun`:

```python
class ResearchRun(BaseModel):
    ...
    paper_items: list[ResearchRunPaperItem] = Field(default_factory=list)
```

Do not add a `completed_with_missing_note` status in this milestone. If note generation fails, mark that item `failed` and continue the remaining items.

## Task 1: Add Item-Level Research Run Schemas

**Files:**

- Modify: `app/research_workflow/schemas.py`
- Test: `tests/test_research_run_service.py`

- [ ] **Step 1: Add schema tests**

Add `Path` to the imports at the top of `tests/test_research_run_service.py`:

```python
from pathlib import Path
```

Then append these tests to `tests/test_research_run_service.py`:

```python
def test_research_run_model_defaults_to_no_paper_items():
    now = datetime.now(timezone.utc)
    run = ResearchRun(
        run_id="run_20260609_000001",
        collection_id="COLL123",
        collection_name="IRSTD",
        goal="Create a review",
        steps=build_default_steps(),
        created_at=now,
        updated_at=now,
    )

    assert run.paper_items == []


def test_research_run_paper_item_tracks_item_lifecycle():
    from app.research_workflow.schemas import (
        ResearchRunPaperArtifact,
        ResearchRunPaperItem,
    )

    now = datetime.now(timezone.utc)
    item = ResearchRunPaperItem(
        item_id="zotero_ABCD1234",
        title="Grounding DINO for Infrared Small Target Detection",
        zotero_item_id="ABCD1234",
        paper_id="paper_20260609_001",
        pdf_path="app/storage/papers/demo.pdf",
        metadata={"doi": "10.1234/demo", "year": 2025},
        status="completed",
        progress=1.0,
        artifacts=[
            ResearchRunPaperArtifact(
                label="Paper Note",
                path="ResearchAgent/Runs/demo/papers/paper_20260609_001.md",
                kind="markdown",
            )
        ],
        created_at=now,
        updated_at=now,
        started_at=now,
        completed_at=now,
    )

    assert item.item_id == "zotero_ABCD1234"
    assert item.status == "completed"
    assert item.artifacts[0].kind == "markdown"
```

- [ ] **Step 2: Run schema tests and verify they fail**

Run:

```powershell
& 'D:\Hcworkspace\Anoconda3\envs\research_agent\python.exe' -m pytest tests/test_research_run_service.py::test_research_run_model_defaults_to_no_paper_items tests/test_research_run_service.py::test_research_run_paper_item_tracks_item_lifecycle -q
```

Expected: FAIL with `ImportError` or validation error because `ResearchRunPaperItem` and `paper_items` do not exist yet.

- [ ] **Step 3: Implement schema additions**

Modify `app/research_workflow/schemas.py`.

Add `Any` to the imports:

```python
from typing import Any, Literal
```

Add these models after `ResearchRunArtifact`:

```python
ResearchRunPaperStatus = Literal["queued", "running", "completed", "failed", "skipped"]


class ResearchRunPaperArtifact(BaseModel):
    label: str
    path: str
    kind: Literal["pdf", "markdown", "json", "vector_index"]


class ResearchRunPaperItem(BaseModel):
    item_id: str
    title: str
    zotero_item_id: str
    paper_id: str | None = None
    pdf_path: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    status: ResearchRunPaperStatus = "queued"
    progress: float = Field(default=0.0, ge=0.0, le=1.0)
    error: str | None = None
    artifacts: list[ResearchRunPaperArtifact] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime
    started_at: datetime | None = None
    completed_at: datetime | None = None
```

Add this field to `ResearchRun` after `artifacts`:

```python
    paper_items: list[ResearchRunPaperItem] = Field(default_factory=list)
```

- [ ] **Step 4: Run focused schema tests**

Run:

```powershell
& 'D:\Hcworkspace\Anoconda3\envs\research_agent\python.exe' -m pytest tests/test_research_run_service.py::test_research_run_model_defaults_to_no_paper_items tests/test_research_run_service.py::test_research_run_paper_item_tracks_item_lifecycle -q
```

Expected: PASS.

- [ ] **Step 5: Commit Task 1**

Run:

```powershell
git add app/research_workflow/schemas.py tests/test_research_run_service.py
git commit -m "feat: add research run paper item schemas"
```

## Task 2: Add Zotero Collection Intake Service

**Files:**

- Create: `app/research_workflow/zotero_intake.py`
- Test: `tests/test_zotero_intake.py`

- [ ] **Step 1: Write intake tests**

Create `tests/test_zotero_intake.py`:

```python
from pathlib import Path

from app.research_workflow.zotero_intake import (
    CollectionIntakeService,
    ZoteroAttachment,
    ZoteroCollectionItem,
    ZoteroLocalHttpClient,
    resolve_first_existing_pdf,
)


class FakeZoteroClient:
    def __init__(self, items):
        self.items = items
        self.seen_collection_ids = []

    def list_collection_items(self, collection_id: str):
        self.seen_collection_ids.append(collection_id)
        return self.items


def test_collection_intake_limits_and_normalizes_items(tmp_path):
    pdf_a = tmp_path / "a.pdf"
    pdf_b = tmp_path / "b.pdf"
    pdf_a.write_bytes(b"%PDF fake a")
    pdf_b.write_bytes(b"%PDF fake b")
    client = FakeZoteroClient(
        [
            ZoteroCollectionItem(
                key="A1",
                title="Paper A",
                creators=["Alice", "Bob"],
                year=2025,
                doi="10.1/a",
                url="https://example.test/a",
                attachments=[ZoteroAttachment(key="ATT1", title="A PDF", path=str(pdf_a))],
                raw={"itemType": "journalArticle"},
            ),
            ZoteroCollectionItem(
                key="B2",
                title="Paper B",
                creators=[],
                year=None,
                doi=None,
                url=None,
                attachments=[ZoteroAttachment(key="ATT2", title="B PDF", path=str(pdf_b))],
                raw={},
            ),
        ]
    )
    service = CollectionIntakeService(client)

    items = service.collect_items("COLL123", max_papers=1)

    assert client.seen_collection_ids == ["COLL123"]
    assert len(items) == 1
    assert items[0].item_id == "zotero_A1"
    assert items[0].zotero_item_id == "A1"
    assert items[0].title == "Paper A"
    assert items[0].pdf_path == str(pdf_a)
    assert items[0].metadata["creators"] == ["Alice", "Bob"]
    assert items[0].metadata["doi"] == "10.1/a"
    assert items[0].status == "queued"


def test_collection_intake_marks_missing_pdf_as_skipped():
    client = FakeZoteroClient(
        [
            ZoteroCollectionItem(
                key="NOFILE",
                title="Missing PDF Paper",
                attachments=[ZoteroAttachment(key="ATT", title="Missing", path="Z:/missing.pdf")],
                raw={},
            )
        ]
    )
    service = CollectionIntakeService(client)

    items = service.collect_items("COLL123", max_papers=5)

    assert items[0].status == "skipped"
    assert items[0].pdf_path is None
    assert "No local PDF attachment found" in items[0].error


def test_resolve_first_existing_pdf_handles_absolute_and_file_uri(tmp_path):
    pdf = tmp_path / "paper.pdf"
    pdf.write_bytes(b"%PDF fake")

    assert resolve_first_existing_pdf([str(pdf)]) == str(pdf)
    assert resolve_first_existing_pdf([pdf.as_uri()]) == str(pdf)
    assert resolve_first_existing_pdf(["", "Z:/missing.pdf"]) is None


def test_zotero_local_http_client_normalizes_local_api_payload(monkeypatch):
    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return [
                {
                    "key": "A1",
                    "data": {
                        "title": "Paper A",
                        "creators": [
                            {"firstName": "Alice", "lastName": "Zhang"},
                            {"name": "Research Group"},
                        ],
                        "date": "2025-04-01",
                        "DOI": "10.1/a",
                        "url": "https://example.test/a",
                    },
                    "links": {
                        "attachment": {
                            "href": "file:///C:/Users/HC/Zotero/storage/A1/paper.pdf"
                        }
                    },
                }
            ]

    calls = []

    def fake_get(url, timeout):
        calls.append((url, timeout))
        return FakeResponse()

    monkeypatch.setattr("httpx.get", fake_get)
    client = ZoteroLocalHttpClient(base_url="http://127.0.0.1:23119/api")

    items = client.list_collection_items("COLL123")

    assert calls[0][0].endswith("/collections/COLL123/items")
    assert items[0].key == "A1"
    assert items[0].title == "Paper A"
    assert items[0].creators == ["Alice Zhang", "Research Group"]
    assert items[0].year == 2025
    assert items[0].doi == "10.1/a"
    assert items[0].attachments[0].path == "file:///C:/Users/HC/Zotero/storage/A1/paper.pdf"
```

- [ ] **Step 2: Run intake tests and verify they fail**

Run:

```powershell
& 'D:\Hcworkspace\Anoconda3\envs\research_agent\python.exe' -m pytest tests/test_zotero_intake.py -q
```

Expected: FAIL with `ModuleNotFoundError: No module named 'app.research_workflow.zotero_intake'`.

- [ ] **Step 3: Implement `zotero_intake.py`**

Create `app/research_workflow/zotero_intake.py`:

```python
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Protocol
from urllib.parse import unquote, urlparse

import httpx
from pydantic import BaseModel, Field

from app.research_workflow.schemas import ResearchRunPaperItem


class ZoteroAttachment(BaseModel):
    key: str
    title: str = ""
    path: str | None = None
    content_type: str | None = None
    raw: dict[str, Any] = Field(default_factory=dict)


class ZoteroCollectionItem(BaseModel):
    key: str
    title: str
    creators: list[str] = Field(default_factory=list)
    year: int | None = None
    doi: str | None = None
    url: str | None = None
    attachments: list[ZoteroAttachment] = Field(default_factory=list)
    raw: dict[str, Any] = Field(default_factory=dict)


class ZoteroCollectionClient(Protocol):
    def list_collection_items(self, collection_id: str) -> list[ZoteroCollectionItem]:
        ...


def resolve_first_existing_pdf(paths: list[str | None]) -> str | None:
    for raw_path in paths:
        if not raw_path:
            continue
        candidate = _normalize_pdf_path(raw_path)
        if candidate and candidate.suffix.lower() == ".pdf" and candidate.is_file():
            return str(candidate)
    return None


def _normalize_pdf_path(raw_path: str) -> Path | None:
    parsed = urlparse(raw_path)
    if parsed.scheme == "file":
        if parsed.netloc and parsed.netloc not in {"", "localhost"}:
            text = f"//{parsed.netloc}{parsed.path}"
        else:
            text = parsed.path
        return Path(unquote(text))
    if parsed.scheme and parsed.scheme != "file":
        return None
    return Path(raw_path).expanduser()


class ZoteroLocalHttpClient:
    def __init__(self, base_url: str = "http://127.0.0.1:23119/api", timeout: float = 10.0) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def list_collection_items(self, collection_id: str) -> list[ZoteroCollectionItem]:
        url = f"{self.base_url}/collections/{collection_id}/items"
        response = httpx.get(url, timeout=self.timeout)
        response.raise_for_status()
        payload = response.json()
        return [_item_from_local_api(raw) for raw in payload]


def _item_from_local_api(raw: dict[str, Any]) -> ZoteroCollectionItem:
    data = raw.get("data") or raw
    links = raw.get("links") or {}
    attachments = _attachments_from_local_payload(raw, data, links)
    return ZoteroCollectionItem(
        key=str(raw.get("key") or data.get("key") or ""),
        title=str(data.get("title") or "Untitled Zotero item"),
        creators=_creators_from_data(data),
        year=_year_from_date(data.get("date")),
        doi=data.get("DOI") or data.get("doi"),
        url=data.get("url"),
        attachments=attachments,
        raw=raw,
    )


def _attachments_from_local_payload(
    raw: dict[str, Any],
    data: dict[str, Any],
    links: dict[str, Any],
) -> list[ZoteroAttachment]:
    attachments: list[ZoteroAttachment] = []
    for raw_attachment in raw.get("attachments", []) or data.get("attachments", []):
        attachment_data = raw_attachment.get("data") or raw_attachment
        attachments.append(
            ZoteroAttachment(
                key=str(raw_attachment.get("key") or attachment_data.get("key") or ""),
                title=str(attachment_data.get("title") or ""),
                path=attachment_data.get("path") or attachment_data.get("localPath"),
                content_type=attachment_data.get("contentType"),
                raw=raw_attachment,
            )
        )
    attachment_link = links.get("attachment")
    if isinstance(attachment_link, dict) and attachment_link.get("href"):
        attachments.append(
            ZoteroAttachment(
                key="attachment_link",
                title="Zotero attachment link",
                path=str(attachment_link["href"]),
                raw=attachment_link,
            )
        )
    return attachments


def _creators_from_data(data: dict[str, Any]) -> list[str]:
    creators: list[str] = []
    for creator in data.get("creators", []) or []:
        if creator.get("name"):
            creators.append(str(creator["name"]))
            continue
        name = " ".join(
            part
            for part in [creator.get("firstName"), creator.get("lastName")]
            if part
        ).strip()
        if name:
            creators.append(name)
    return creators


def _year_from_date(value: Any) -> int | None:
    if not value:
        return None
    text = str(value)
    for token in text.replace("/", "-").split("-"):
        if token.isdigit() and len(token) == 4:
            return int(token)
    return None


class CollectionIntakeService:
    def __init__(self, client: ZoteroCollectionClient) -> None:
        self._client = client

    def collect_items(self, collection_id: str, max_papers: int) -> list[ResearchRunPaperItem]:
        now = datetime.now(timezone.utc)
        items = self._client.list_collection_items(collection_id)[:max_papers]
        output: list[ResearchRunPaperItem] = []
        for item in items:
            pdf_path = resolve_first_existing_pdf([attachment.path for attachment in item.attachments])
            metadata = {
                "creators": item.creators,
                "year": item.year,
                "doi": item.doi,
                "url": item.url,
                "attachments": [attachment.model_dump(mode="json") for attachment in item.attachments],
            }
            if pdf_path:
                status = "queued"
                error = None
                progress = 0.0
            else:
                status = "skipped"
                error = "No local PDF attachment found"
                progress = 1.0
            output.append(
                ResearchRunPaperItem(
                    item_id=f"zotero_{item.key}",
                    title=item.title,
                    zotero_item_id=item.key,
                    pdf_path=pdf_path,
                    metadata=metadata,
                    status=status,
                    progress=progress,
                    error=error,
                    created_at=now,
                    updated_at=now,
                    completed_at=now if status == "skipped" else None,
                )
            )
        return output
```

- [ ] **Step 4: Run intake tests**

Run:

```powershell
& 'D:\Hcworkspace\Anoconda3\envs\research_agent\python.exe' -m pytest tests/test_zotero_intake.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit Task 2**

Run:

```powershell
git add app/research_workflow/zotero_intake.py tests/test_zotero_intake.py
git commit -m "feat: add zotero collection intake service"
```

## Task 3: Add Local Paper Processing Service

**Files:**

- Create: `app/research_workflow/paper_processing.py`
- Test: `tests/test_paper_processing_service.py`

- [ ] **Step 1: Write paper-processing tests**

Create `tests/test_paper_processing_service.py`:

```python
from datetime import datetime, timezone
from pathlib import Path

from app.research_workflow.paper_processing import PaperProcessingService
from app.research_workflow.schemas import ResearchRunPaperItem
from app.schemas import PaperParseResult, Section


class FakeEmbeddingClient:
    device = "cpu"
    batch_size = 2

    def embed_texts(self, texts):
        return [[1.0, 0.0, 0.0] for _ in texts]


class FakeVectorStore:
    def __init__(self):
        self.added = []

    def add_chunks(self, chunks, embeddings):
        self.added.append((chunks, embeddings))
        return len(chunks)

    def backend_name(self):
        return "fake"

    def metadata(self):
        return {"store_path": "fake/vector_store.json", "chunk_count": 2}


def _item(pdf_path: Path) -> ResearchRunPaperItem:
    now = datetime.now(timezone.utc)
    return ResearchRunPaperItem(
        item_id="zotero_A1",
        title="Paper A",
        zotero_item_id="A1",
        pdf_path=str(pdf_path),
        created_at=now,
        updated_at=now,
    )


def test_paper_processing_copies_parses_indexes_and_generates_note(tmp_path):
    source_pdf = tmp_path / "source.pdf"
    source_pdf.write_bytes(b"%PDF fake")
    upload_dir = tmp_path / "papers"
    metadata_dir = tmp_path / "metadata"
    note_dir = tmp_path / "notes"
    vault_run_dir = tmp_path / "vault" / "ResearchAgent" / "Runs" / "demo"
    vault_run_dir.mkdir(parents=True)

    def fake_parse(pdf_path, paper_id):
        return PaperParseResult(
            paper_id=paper_id,
            title="Parsed Paper A",
            abstract="Abstract A",
            sections=[Section(heading="Method", content="This method section is long enough to chunk.")],
            full_text="This method section is long enough to chunk.",
            pdf_path=pdf_path,
        )

    service = PaperProcessingService(
        upload_dir=upload_dir,
        metadata_dir=metadata_dir,
        note_dir=note_dir,
        vector_store=FakeVectorStore(),
        embedding_client=FakeEmbeddingClient(),
        parse_pdf_func=fake_parse,
        note_generator_func=lambda paper_id, metadata_dir: "# Note for Paper A",
        paper_id_generator=lambda upload_dir: "paper_20260609_001",
    )

    result = service.process_item(_item(source_pdf), vault_run_dir)

    assert result.item.status == "completed"
    assert result.item.paper_id == "paper_20260609_001"
    assert Path(result.item.pdf_path).is_file()
    assert (metadata_dir / "paper_20260609_001_parsed.json").is_file()
    assert (note_dir / "paper_20260609_001_note.md").is_file()
    assert (vault_run_dir / "papers" / "paper_20260609_001.md").read_text(encoding="utf-8") == "# Note for Paper A"
    assert result.chunk_count == 1
    assert result.note_path.endswith("paper_20260609_001_note.md")


def test_paper_processing_failed_parse_returns_failed_item(tmp_path):
    source_pdf = tmp_path / "source.pdf"
    source_pdf.write_bytes(b"%PDF fake")

    def failing_parse(pdf_path, paper_id):
        raise ValueError("bad pdf")

    service = PaperProcessingService(
        upload_dir=tmp_path / "papers",
        metadata_dir=tmp_path / "metadata",
        note_dir=tmp_path / "notes",
        vector_store=FakeVectorStore(),
        embedding_client=FakeEmbeddingClient(),
        parse_pdf_func=failing_parse,
        note_generator_func=lambda paper_id, metadata_dir: "# not reached",
        paper_id_generator=lambda upload_dir: "paper_20260609_001",
    )

    result = service.process_item(_item(source_pdf), tmp_path / "vault")

    assert result.item.status == "failed"
    assert result.item.error == "bad pdf"
    assert result.chunk_count == 0
```

- [ ] **Step 2: Run paper-processing tests and verify they fail**

Run:

```powershell
& 'D:\Hcworkspace\Anoconda3\envs\research_agent\python.exe' -m pytest tests/test_paper_processing_service.py -q
```

Expected: FAIL with `ModuleNotFoundError: No module named 'app.research_workflow.paper_processing'`.

- [ ] **Step 3: Implement `paper_processing.py`**

Create `app/research_workflow/paper_processing.py`:

```python
from __future__ import annotations

import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Protocol

from pydantic import BaseModel

from app.research_workflow.schemas import (
    ResearchRunPaperArtifact,
    ResearchRunPaperItem,
)
from app.schemas import PaperParseResult
from app.services.chunker import chunk_paper
from app.services.markdown_exporter import save_markdown
from app.services.pdf_parser import generate_paper_id, parse_pdf, save_parse_result


class EmbeddingProvider(Protocol):
    device: str
    batch_size: int

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        ...


class VectorStoreProvider(Protocol):
    def add_chunks(self, chunks, embeddings: list[list[float]]) -> int:
        ...

    def backend_name(self) -> str:
        ...

    def metadata(self) -> dict:
        ...


class PaperProcessingResult(BaseModel):
    item: ResearchRunPaperItem
    chunk_count: int = 0
    note_path: str | None = None
    vector_backend: str | None = None


class PaperProcessingService:
    def __init__(
        self,
        upload_dir: str | Path,
        metadata_dir: str | Path,
        note_dir: str | Path,
        vector_store: VectorStoreProvider,
        embedding_client: EmbeddingProvider,
        parse_pdf_func: Callable[[str, str], PaperParseResult] = parse_pdf,
        note_generator_func: Callable[[str, str], str] | None = None,
        paper_id_generator: Callable[[str], str] = generate_paper_id,
    ) -> None:
        self.upload_dir = Path(upload_dir)
        self.metadata_dir = Path(metadata_dir)
        self.note_dir = Path(note_dir)
        self.vector_store = vector_store
        self.embedding_client = embedding_client
        self.parse_pdf_func = parse_pdf_func
        self.note_generator_func = note_generator_func or self._generate_note
        self.paper_id_generator = paper_id_generator

    def process_item(self, item: ResearchRunPaperItem, run_output_dir: str | Path) -> PaperProcessingResult:
        started_at = datetime.now(timezone.utc)
        running = item.model_copy(
            update={"status": "running", "progress": 0.05, "started_at": started_at, "updated_at": started_at}
        )
        try:
            if not running.pdf_path:
                raise FileNotFoundError("No local PDF attachment found")
            paper_id = self.paper_id_generator(str(self.upload_dir))
            stored_pdf = self._copy_pdf(Path(running.pdf_path), paper_id)
            parsed = self.parse_pdf_func(str(stored_pdf), paper_id)
            metadata_path = save_parse_result(parsed, str(self.metadata_dir))
            chunks = chunk_paper(parsed)
            if not chunks:
                raise ValueError("Paper content produced no indexable chunks")
            embeddings = self.embedding_client.embed_texts([chunk.content for chunk in chunks])
            self.vector_store.add_chunks(chunks, embeddings)
            markdown = self.note_generator_func(paper_id, str(self.metadata_dir))
            note_path = save_markdown(paper_id, markdown, str(self.note_dir))
            run_note_path = self._write_run_paper_note(run_output_dir, paper_id, markdown)
            completed_at = datetime.now(timezone.utc)
            completed = running.model_copy(
                update={
                    "paper_id": paper_id,
                    "pdf_path": str(stored_pdf),
                    "status": "completed",
                    "progress": 1.0,
                    "error": None,
                    "artifacts": [
                        ResearchRunPaperArtifact(label="PDF", path=str(stored_pdf), kind="pdf"),
                        ResearchRunPaperArtifact(label="Parsed Metadata", path=str(metadata_path), kind="json"),
                        ResearchRunPaperArtifact(label="Paper Note", path=str(run_note_path), kind="markdown"),
                        ResearchRunPaperArtifact(label="Vector Index", path=self.vector_store.metadata().get("store_path", ""), kind="vector_index"),
                    ],
                    "updated_at": completed_at,
                    "completed_at": completed_at,
                }
            )
            return PaperProcessingResult(
                item=completed,
                chunk_count=len(chunks),
                note_path=str(note_path),
                vector_backend=self.vector_store.backend_name(),
            )
        except Exception as exc:
            failed_at = datetime.now(timezone.utc)
            failed = running.model_copy(
                update={
                    "status": "failed",
                    "progress": 1.0,
                    "error": str(exc),
                    "updated_at": failed_at,
                    "completed_at": failed_at,
                }
            )
            return PaperProcessingResult(item=failed)

    def _copy_pdf(self, source: Path, paper_id: str) -> Path:
        if not source.is_file():
            raise FileNotFoundError(f"PDF file not found: {source}")
        self.upload_dir.mkdir(parents=True, exist_ok=True)
        suffix = source.suffix if source.suffix.lower() == ".pdf" else ".pdf"
        target = self.upload_dir / f"{paper_id}{suffix}"
        shutil.copy2(source, target)
        return target

    def _write_run_paper_note(self, run_output_dir: str | Path, paper_id: str, markdown: str) -> Path:
        papers_dir = Path(run_output_dir) / "papers"
        papers_dir.mkdir(parents=True, exist_ok=True)
        path = papers_dir / f"{paper_id}.md"
        path.write_text(markdown, encoding="utf-8")
        return path

    def _generate_note(self, paper_id: str, metadata_dir: str) -> str:
        from app.services.note_generator import generate_note

        return generate_note(paper_id, metadata_dir=metadata_dir)
```

- [ ] **Step 4: Run paper-processing tests**

Run:

```powershell
& 'D:\Hcworkspace\Anoconda3\envs\research_agent\python.exe' -m pytest tests/test_paper_processing_service.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit Task 3**

Run:

```powershell
git add app/research_workflow/paper_processing.py tests/test_paper_processing_service.py
git commit -m "feat: add local paper processing service"
```

## Task 4: Update Knowledge Pack Summary, Trace, and Tool Calls

**Files:**

- Modify: `app/research_workflow/knowledge_pack.py`
- Test: `tests/test_research_run_service.py`

- [ ] **Step 1: Add Knowledge Pack update tests**

Append these tests to `tests/test_research_run_service.py`:

```python
def test_knowledge_pack_update_rewrites_summary_with_paper_counts(tmp_path):
    from app.research_workflow.knowledge_pack import update_knowledge_pack_run_files
    from app.research_workflow.schemas import ResearchRunPaperItem

    now = datetime.now(timezone.utc)
    run = ResearchRun(
        run_id="run_20260609_000001",
        collection_id="COLL123",
        collection_name="IRSTD",
        goal="Create an IRSTD review",
        steps=build_default_steps(),
        paper_items=[
            ResearchRunPaperItem(
                item_id="zotero_A1",
                title="Paper A",
                zotero_item_id="A1",
                paper_id="paper_20260609_001",
                status="completed",
                progress=1.0,
                created_at=now,
                updated_at=now,
            ),
            ResearchRunPaperItem(
                item_id="zotero_B2",
                title="Paper B",
                zotero_item_id="B2",
                status="skipped",
                progress=1.0,
                error="No local PDF attachment found",
                created_at=now,
                updated_at=now,
            ),
        ],
        created_at=now,
        updated_at=now,
    )
    run = create_knowledge_pack_skeleton(run, tmp_path)

    update_knowledge_pack_run_files(run)

    summary = (Path(run.output_dir) / "00 Run Summary.md").read_text(encoding="utf-8")
    trace = json.loads((Path(run.output_dir) / "assets" / "trace.json").read_text(encoding="utf-8"))
    assert "- Completed Papers: 1" in summary
    assert "- Skipped Papers: 1" in summary
    assert "Paper A" in summary
    assert "No local PDF attachment found" in summary
    assert trace["paper_items"][0]["paper_id"] == "paper_20260609_001"


def test_append_tool_call_record_writes_jsonl(tmp_path):
    from app.research_workflow.knowledge_pack import append_tool_call_record

    now = datetime.now(timezone.utc)
    run = ResearchRun(
        run_id="run_20260609_000001",
        collection_id="COLL123",
        collection_name="IRSTD",
        goal="Create an IRSTD review",
        steps=build_default_steps(),
        created_at=now,
        updated_at=now,
    )
    run = create_knowledge_pack_skeleton(run, tmp_path)

    append_tool_call_record(
        run,
        {
            "tool_name": "zotero.list_collection_items",
            "provider": "local_http",
            "status": "completed",
            "result_summary": "2 items",
        },
    )

    lines = (Path(run.output_dir) / "assets" / "tool-calls.jsonl").read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1
    payload = json.loads(lines[0])
    assert payload["run_id"] == "run_20260609_000001"
    assert payload["tool_name"] == "zotero.list_collection_items"
```

- [ ] **Step 2: Run Knowledge Pack tests and verify they fail**

Run:

```powershell
& 'D:\Hcworkspace\Anoconda3\envs\research_agent\python.exe' -m pytest tests/test_research_run_service.py::test_knowledge_pack_update_rewrites_summary_with_paper_counts tests/test_research_run_service.py::test_append_tool_call_record_writes_jsonl -q
```

Expected: FAIL with import errors for `update_knowledge_pack_run_files` and `append_tool_call_record`.

- [ ] **Step 3: Implement Knowledge Pack update helpers**

Modify `app/research_workflow/knowledge_pack.py`.

Add `datetime` import:

```python
from datetime import datetime, timezone
```

Add these public functions after `create_knowledge_pack_skeleton`:

```python
def update_knowledge_pack_run_files(run: ResearchRun) -> None:
    output_dir = Path(run.output_dir)
    if not output_dir:
        return
    (output_dir / "00 Run Summary.md").write_text(_render_summary(run), encoding="utf-8")
    assets_dir = output_dir / "assets"
    assets_dir.mkdir(parents=True, exist_ok=True)
    (assets_dir / "trace.json").write_text(
        json.dumps(_trace_payload(run), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def append_tool_call_record(run: ResearchRun, record: dict[str, object]) -> None:
    output_dir = Path(run.output_dir)
    assets_dir = output_dir / "assets"
    assets_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "run_id": run.run_id,
        "recorded_at": datetime.now(timezone.utc).isoformat(),
        **record,
    }
    with (assets_dir / "tool-calls.jsonl").open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False) + "\n")
```

Replace `_render_summary` with:

```python
def _render_summary(run: ResearchRun) -> str:
    completed = sum(1 for item in run.paper_items if item.status == "completed")
    failed = sum(1 for item in run.paper_items if item.status == "failed")
    skipped = sum(1 for item in run.paper_items if item.status == "skipped")
    lines = [
        f"# Research Run: {run.collection_name}",
        "",
        f"- Run ID: {run.run_id}",
        f"- Collection ID: {run.collection_id}",
        f"- Collection Name: {run.collection_name}",
        f"- Goal: {run.goal}",
        f"- Status: {run.status}",
        f"- Progress: {run.progress:.0%}",
        f"- Max Papers: {run.options.max_papers}",
        f"- Completed Papers: {completed}",
        f"- Failed Papers: {failed}",
        f"- Skipped Papers: {skipped}",
        "",
        "## Steps",
        "",
    ]
    lines.extend(f"- {step.agent}: {step.status} ({step.progress:.0%})" for step in run.steps)
    lines.extend(["", "## Papers", ""])
    if not run.paper_items:
        lines.append("- No paper items have been collected yet.")
    else:
        for item in run.paper_items:
            paper_label = item.paper_id or "not synced"
            error = f" - {item.error}" if item.error else ""
            lines.append(f"- {item.title} [{item.status}] `{paper_label}`{error}")
    lines.append("")
    return "\n".join(lines)
```

Update `_trace_payload` to include `progress`, `artifacts`, and `paper_items`:

```python
def _trace_payload(run: ResearchRun) -> dict[str, object]:
    return {
        "run_id": run.run_id,
        "collection_id": run.collection_id,
        "collection_name": run.collection_name,
        "goal": run.goal,
        "status": run.status,
        "progress": run.progress,
        "steps": [step.model_dump(mode="json") for step in run.steps],
        "artifacts": [artifact.model_dump(mode="json") for artifact in run.artifacts],
        "paper_items": [item.model_dump(mode="json") for item in run.paper_items],
    }
```

- [ ] **Step 4: Run Knowledge Pack tests**

Run:

```powershell
& 'D:\Hcworkspace\Anoconda3\envs\research_agent\python.exe' -m pytest tests/test_research_run_service.py::test_knowledge_pack_update_rewrites_summary_with_paper_counts tests/test_research_run_service.py::test_append_tool_call_record_writes_jsonl -q
```

Expected: PASS.

- [ ] **Step 5: Commit Task 4**

Run:

```powershell
git add app/research_workflow/knowledge_pack.py tests/test_research_run_service.py
git commit -m "feat: update research run knowledge pack trace"
```

## Task 5: Orchestrate Local Collection Execution

**Files:**

- Modify: `app/research_workflow/service.py`
- Test: `tests/test_research_run_service.py`

- [ ] **Step 1: Add orchestration tests**

Append this test to `tests/test_research_run_service.py`:

```python
def test_research_run_service_execute_local_run_processes_success_and_skip(tmp_path):
    from app.research_workflow.paper_processing import PaperProcessingResult
    from app.research_workflow.schemas import ResearchRunPaperItem

    class FakeIntake:
        def collect_items(self, collection_id, max_papers):
            now = datetime.now(timezone.utc)
            return [
                ResearchRunPaperItem(
                    item_id="zotero_A1",
                    title="Paper A",
                    zotero_item_id="A1",
                    pdf_path=str(tmp_path / "a.pdf"),
                    created_at=now,
                    updated_at=now,
                ),
                ResearchRunPaperItem(
                    item_id="zotero_B2",
                    title="Paper B",
                    zotero_item_id="B2",
                    status="skipped",
                    progress=1.0,
                    error="No local PDF attachment found",
                    created_at=now,
                    updated_at=now,
                    completed_at=now,
                ),
            ]

    class FakeProcessor:
        def process_item(self, item, run_output_dir):
            completed = item.model_copy(
                update={
                    "paper_id": "paper_20260609_001",
                    "status": "completed",
                    "progress": 1.0,
                    "updated_at": datetime.now(timezone.utc),
                    "completed_at": datetime.now(timezone.utc),
                }
            )
            return PaperProcessingResult(item=completed, chunk_count=2, note_path="note.md", vector_backend="fake")

    store = FileResearchRunStore(tmp_path / "runs.json")
    service = ResearchRunService(store=store, vault_root=tmp_path / "vault")
    run = service.create_run(
        ResearchRunCreateRequest(
            collection_id="COLL123",
            collection_name="IRSTD",
            options=ResearchRunOptions(max_papers=2),
        )
    )

    executed = service.execute_local_run(run.run_id, intake_service=FakeIntake(), paper_processor=FakeProcessor())

    assert executed.status == "completed"
    assert executed.progress == 1.0
    assert [item.status for item in executed.paper_items] == ["completed", "skipped"]
    assert executed.steps[0].status == "completed"
    assert executed.steps[1].status == "completed"
    assert store.get(run.run_id).paper_items[0].paper_id == "paper_20260609_001"
    summary = (Path(executed.output_dir) / "00 Run Summary.md").read_text(encoding="utf-8")
    assert "- Completed Papers: 1" in summary
    assert "- Skipped Papers: 1" in summary


def test_research_run_service_execute_local_run_keeps_going_after_item_failure(tmp_path):
    from app.research_workflow.paper_processing import PaperProcessingResult
    from app.research_workflow.schemas import ResearchRunPaperItem

    class FakeIntake:
        def collect_items(self, collection_id, max_papers):
            now = datetime.now(timezone.utc)
            return [
                ResearchRunPaperItem(item_id="zotero_A1", title="Paper A", zotero_item_id="A1", pdf_path="a.pdf", created_at=now, updated_at=now),
                ResearchRunPaperItem(item_id="zotero_B2", title="Paper B", zotero_item_id="B2", pdf_path="b.pdf", created_at=now, updated_at=now),
            ]

    class FakeProcessor:
        def process_item(self, item, run_output_dir):
            now = datetime.now(timezone.utc)
            if item.zotero_item_id == "A1":
                return PaperProcessingResult(item=item.model_copy(update={"status": "failed", "progress": 1.0, "error": "parse failed", "updated_at": now, "completed_at": now}))
            return PaperProcessingResult(item=item.model_copy(update={"paper_id": "paper_20260609_002", "status": "completed", "progress": 1.0, "updated_at": now, "completed_at": now}), chunk_count=1)

    store = FileResearchRunStore(tmp_path / "runs.json")
    service = ResearchRunService(store=store, vault_root=tmp_path / "vault")
    run = service.create_run(
        ResearchRunCreateRequest(collection_id="COLL123", collection_name="IRSTD")
    )

    executed = service.execute_local_run(run.run_id, intake_service=FakeIntake(), paper_processor=FakeProcessor())

    assert executed.status == "completed"
    assert [item.status for item in executed.paper_items] == ["failed", "completed"]
    assert executed.paper_items[0].error == "parse failed"
```

- [ ] **Step 2: Run orchestration tests and verify they fail**

Run:

```powershell
& 'D:\Hcworkspace\Anoconda3\envs\research_agent\python.exe' -m pytest tests/test_research_run_service.py::test_research_run_service_execute_local_run_processes_success_and_skip tests/test_research_run_service.py::test_research_run_service_execute_local_run_keeps_going_after_item_failure -q
```

Expected: FAIL with `AttributeError: 'ResearchRunService' object has no attribute 'execute_local_run'`.

- [ ] **Step 3: Implement service orchestration**

Modify `app/research_workflow/service.py`.

Add imports:

```python
from app.config import settings
from app.research_workflow.knowledge_pack import (
    append_tool_call_record,
    update_knowledge_pack_run_files,
)
from app.research_workflow.paper_processing import PaperProcessingService
from app.research_workflow.zotero_intake import (
    CollectionIntakeService,
    ZoteroLocalHttpClient,
)
from app.services.embedding_client import EmbeddingClient
from app.services.vector_store import VectorStore
```

Add this method to `ResearchRunService` after `get_run`:

```python
    def execute_local_run(
        self,
        run_id: str,
        intake_service: CollectionIntakeService | None = None,
        paper_processor: PaperProcessingService | None = None,
    ) -> ResearchRun:
        run = self.get_run(run_id)
        if run.status in {"completed", "failed", "cancelled"}:
            raise ResearchRunConflictError(
                f"Research run {run.run_id} cannot be executed from status {run.status}"
            )

        now = datetime.now(timezone.utc)
        run = create_knowledge_pack_skeleton(
            run.model_copy(update={"status": "running", "started_at": run.started_at or now, "updated_at": now}),
            self._vault_root,
        )
        run = self._mark_step(run, "collection_intake", "running", 0.0, "Reading Zotero collection")
        self._store.upsert(run)
        update_knowledge_pack_run_files(run)

        intake_service = intake_service or CollectionIntakeService(ZoteroLocalHttpClient())
        paper_processor = paper_processor or self._default_paper_processor()

        items = intake_service.collect_items(run.collection_id, run.options.max_papers)
        append_tool_call_record(
            run,
            {
                "tool_name": "zotero.list_collection_items",
                "provider": "local_http",
                "status": "completed",
                "result_summary": f"{len(items)} item(s)",
            },
        )
        run = run.model_copy(update={"paper_items": items, "updated_at": datetime.now(timezone.utc)})
        run = self._mark_step(run, "collection_intake", "completed", 1.0, f"Collected {len(items)} item(s)")
        run = self._mark_step(run, "paper_understanding", "running", 0.0, "Processing local papers")
        self._store.upsert(run)
        update_knowledge_pack_run_files(run)

        processed_items = []
        processable_items = [item for item in items if item.status == "queued"]
        for index, item in enumerate(items, start=1):
            if item.status != "queued":
                processed_items.append(item)
            else:
                result = paper_processor.process_item(item, run.output_dir)
                processed_items.append(result.item)
                append_tool_call_record(
                    run,
                    {
                        "tool_name": "research_agent.process_paper",
                        "provider": "local_service",
                        "status": result.item.status,
                        "arguments": {"zotero_item_id": item.zotero_item_id},
                        "result_summary": result.item.paper_id or result.item.error or "",
                    },
                )
            progress = index / max(len(items), 1)
            run = run.model_copy(
                update={
                    "paper_items": processed_items + items[index:],
                    "progress": round(progress, 3),
                    "updated_at": datetime.now(timezone.utc),
                }
            )
            self._store.upsert(run)
            update_knowledge_pack_run_files(run)

        completed_count = sum(1 for item in processed_items if item.status == "completed")
        failed_count = sum(1 for item in processed_items if item.status == "failed")
        skipped_count = sum(1 for item in processed_items if item.status == "skipped")
        final_status = "completed" if completed_count or skipped_count or not failed_count else "failed"
        completed_at = datetime.now(timezone.utc)
        run = run.model_copy(
            update={
                "status": final_status,
                "progress": 1.0,
                "paper_items": processed_items,
                "updated_at": completed_at,
                "completed_at": completed_at,
                "error": None if final_status == "completed" else "All paper items failed",
            }
        )
        understanding_status = "completed" if completed_count or skipped_count or not processed_items else "failed"
        run = self._mark_step(
            run,
            "paper_understanding",
            understanding_status,
            1.0,
            f"Completed={completed_count}, failed={failed_count}, skipped={skipped_count}",
        )
        self._store.upsert(run)
        update_knowledge_pack_run_files(run)
        return run
```

Add these helper methods before `_cancel_run`:

```python
    def _default_paper_processor(self) -> PaperProcessingService:
        return PaperProcessingService(
            upload_dir=settings.upload_dir,
            metadata_dir=settings.metadata_dir,
            note_dir=settings.note_dir,
            vector_store=VectorStore(),
            embedding_client=EmbeddingClient(),
        )

    def _mark_step(
        self,
        run: ResearchRun,
        step_id: str,
        status: str,
        progress: float,
        message: str,
    ) -> ResearchRun:
        now = datetime.now(timezone.utc)
        steps = []
        for step in run.steps:
            if step.step_id != step_id:
                steps.append(step)
                continue
            update = {
                "status": status,
                "progress": progress,
                "message": message,
            }
            if status == "running" and step.started_at is None:
                update["started_at"] = now
            if status in {"completed", "failed", "cancelled"}:
                update["completed_at"] = now
            steps.append(step.model_copy(update=update))
        return run.model_copy(update={"steps": steps, "updated_at": now})
```

- [ ] **Step 4: Run orchestration tests**

Run:

```powershell
& 'D:\Hcworkspace\Anoconda3\envs\research_agent\python.exe' -m pytest tests/test_research_run_service.py::test_research_run_service_execute_local_run_processes_success_and_skip tests/test_research_run_service.py::test_research_run_service_execute_local_run_keeps_going_after_item_failure -q
```

Expected: PASS.

- [ ] **Step 5: Run all ResearchRun service/store tests**

Run:

```powershell
& 'D:\Hcworkspace\Anoconda3\envs\research_agent\python.exe' -m pytest tests/test_research_run_service.py tests/test_research_run_store.py -q
```

Expected: PASS.

- [ ] **Step 6: Commit Task 5**

Run:

```powershell
git add app/research_workflow/service.py tests/test_research_run_service.py
git commit -m "feat: execute local zotero research runs"
```

## Task 6: Add API Endpoint for Local Execution

**Files:**

- Modify: `app/routers/research_runs.py`
- Test: `tests/test_research_run_router.py`

- [ ] **Step 1: Add router test**

Append this test to `tests/test_research_run_router.py`:

```python
def test_research_run_execute_local_route(tmp_path, monkeypatch):
    service = _override_research_run_service(tmp_path, monkeypatch)

    class FakeIntake:
        def collect_items(self, collection_id, max_papers):
            return []

    class FakeProcessor:
        pass

    try:
        client = TestClient(app)
        created = client.post(
            "/research-runs",
            json={"collection_id": "COLL123", "collection_name": "IRSTD"},
        ).json()

        from app.routers import research_runs as router

        app.dependency_overrides[router.get_collection_intake_service] = lambda: FakeIntake()
        app.dependency_overrides[router.get_paper_processing_service] = lambda: FakeProcessor()

        response = client.post(f"/research-runs/{created['run_id']}/execute-local")

        assert response.status_code == 200
        assert response.json()["status"] == "completed"
        assert response.json()["paper_items"] == []
    finally:
        app.dependency_overrides.clear()
```

- [ ] **Step 2: Run router test and verify it fails**

Run:

```powershell
& 'D:\Hcworkspace\Anoconda3\envs\research_agent\python.exe' -m pytest tests/test_research_run_router.py::test_research_run_execute_local_route -q
```

Expected: FAIL because `/execute-local` and dependency providers do not exist.

- [ ] **Step 3: Implement router dependencies and endpoint**

Modify `app/routers/research_runs.py`.

Add imports:

```python
from app.research_workflow.paper_processing import PaperProcessingService
from app.research_workflow.zotero_intake import CollectionIntakeService, ZoteroLocalHttpClient
from app.services.embedding_client import EmbeddingClient
from app.services.vector_store import VectorStore
```

Add dependency functions after `get_research_run_service`:

```python
def get_collection_intake_service() -> CollectionIntakeService:
    return CollectionIntakeService(ZoteroLocalHttpClient())


def get_paper_processing_service() -> PaperProcessingService:
    return PaperProcessingService(
        upload_dir=settings.upload_dir,
        metadata_dir=settings.metadata_dir,
        note_dir=settings.note_dir,
        vector_store=VectorStore(),
        embedding_client=EmbeddingClient(),
    )
```

Add endpoint before `@router.get("/{run_id}")`:

```python
@router.post("/{run_id}/execute-local", response_model=ResearchRun)
def execute_research_run_local(
    run_id: str,
    service: ResearchRunService = Depends(get_research_run_service),
    intake_service: CollectionIntakeService = Depends(get_collection_intake_service),
    paper_processing_service: PaperProcessingService = Depends(get_paper_processing_service),
) -> ResearchRun:
    try:
        return service.execute_local_run(
            run_id,
            intake_service=intake_service,
            paper_processor=paper_processing_service,
        )
    except ResearchRunNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Research run {run_id} not found",
        ) from exc
    except ResearchRunConflictError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc
```

- [ ] **Step 4: Run router tests**

Run:

```powershell
& 'D:\Hcworkspace\Anoconda3\envs\research_agent\python.exe' -m pytest tests/test_research_run_router.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit Task 6**

Run:

```powershell
git add app/routers/research_runs.py tests/test_research_run_router.py
git commit -m "feat: add local research run execution endpoint"
```

## Task 7: Update Streamlit Research Workflow UI

**Files:**

- Modify: `ui/streamlit_app.py`
- Test: `tests/test_research_workflow_ui_import.py`

- [ ] **Step 1: Add UI source tests**

Append these tests to `tests/test_research_workflow_ui_import.py`:

```python
def test_research_workflow_ui_contains_local_execute_action():
    source = _streamlit_source()

    assert "Process Local Collection" in source
    assert "execute_local_run" in source
    assert "paper_items" in source
    assert "Zotero Item" in source


def test_research_workflow_ui_displays_paper_item_status_columns():
    source = _streamlit_source()

    for token in (
        "Paper Items",
        "item.zotero_item_id",
        "item.paper_id",
        "item.pdf_path",
        "item.error",
    ):
        assert token in source
```

- [ ] **Step 2: Run UI tests and verify they fail**

Run:

```powershell
& 'D:\Hcworkspace\Anoconda3\envs\research_agent\python.exe' -m pytest tests/test_research_workflow_ui_import.py::test_research_workflow_ui_contains_local_execute_action tests/test_research_workflow_ui_import.py::test_research_workflow_ui_displays_paper_item_status_columns -q
```

Expected: FAIL because the UI has no local execution action or paper-item table.

- [ ] **Step 3: Update imports and cached service wiring**

In `ui/streamlit_app.py`, add:

```python
from app.research_workflow.paper_processing import PaperProcessingService
from app.research_workflow.zotero_intake import CollectionIntakeService, ZoteroLocalHttpClient
```

Add cached helpers near `get_research_run_service`:

```python
@st.cache_resource
def get_collection_intake_service():
    return CollectionIntakeService(ZoteroLocalHttpClient())


@st.cache_resource
def get_paper_processing_service():
    return PaperProcessingService(
        upload_dir=settings.upload_dir,
        metadata_dir=settings.metadata_dir,
        note_dir=settings.note_dir,
        vector_store=get_vector_store(),
        embedding_client=get_embedding_client(),
    )
```

- [ ] **Step 4: Add local execution button and item table**

In the `if tab == "Research Workflow":` block, after the selected run is loaded and before artifacts are shown, add:

```python
            col_execute, col_refresh = st.columns(2)
            with col_execute:
                if st.button("Process Local Collection", type="primary", use_container_width=True):
                    try:
                        run = service.execute_local_run(
                            run.run_id,
                            intake_service=get_collection_intake_service(),
                            paper_processor=get_paper_processing_service(),
                        )
                    except Exception as exc:
                        st.error(f"Unable to process local collection: {exc}")
                    else:
                        st.success("Local collection processing completed.")
                        st.session_state["selected_research_run_id"] = run.run_id
                        st.rerun()
            with col_refresh:
                if st.button("Refresh Run", use_container_width=True):
                    st.rerun()

            st.subheader("Paper Items")
            if not run.paper_items:
                st.info("No Zotero paper items have been collected yet.")
            else:
                for item in run.paper_items:
                    with st.expander(f"{item.title} - {item.status}", expanded=item.status != "completed"):
                        st.write(f"Zotero Item: {item.zotero_item_id}")
                        st.write(f"Paper ID: {item.paper_id or 'not synced'}")
                        st.write(f"PDF: {item.pdf_path or 'missing'}")
                        st.progress(item.progress)
                        if item.error:
                            st.error(item.error)
                        for artifact in item.artifacts:
                            st.write(f"{artifact.label}: {artifact.path}")
```

Keep the existing artifact display after this block.

- [ ] **Step 5: Run UI source tests**

Run:

```powershell
& 'D:\Hcworkspace\Anoconda3\envs\research_agent\python.exe' -m pytest tests/test_research_workflow_ui_import.py -q
```

Expected: PASS.

- [ ] **Step 6: Commit Task 7**

Run:

```powershell
git add ui/streamlit_app.py tests/test_research_workflow_ui_import.py
git commit -m "feat: show local collection processing in ui"
```

## Task 8: Milestone 2 Verification and Execution Docs

**Files:**

- Modify: `.Codex/plans/current-plan.md`
- Modify: `.Codex/tasks/current-tasks.md`
- Optional Modify: `docs/README.md`

- [ ] **Step 1: Update current plan and task tracker**

Replace `.Codex/plans/current-plan.md` with:

```markdown
# Milestone 2: Zotero Collection to Local Paper Processing

## Scope

Execute the implementation plan in:

`docs/superpowers/plans/2026-06-09-zotero-collection-processing.md`

Goal: make ResearchRun process a Zotero collection into local parsed/indexed papers and per-paper Knowledge Pack notes with item-level status tracking.

## Constraints

- Do not modify `.env` without explicit user approval.
- Do not bulk delete files or directories.
- Do not delete datasets, checkpoints, outputs, logs, or experiment results.
- Work one task at a time.
- Keep changes scoped to the files listed in the plan.
- Do not revert unrelated dirty worktree changes.
- After each task, run the task-specific verification command and inspect `git diff`.

## Tasks

1. Add item-level Research Run schemas.
2. Add Zotero collection intake service.
3. Add local paper processing service.
4. Update Knowledge Pack summary, trace, and tool calls.
5. Orchestrate local collection execution.
6. Add API endpoint for local execution.
7. Update Streamlit Research Workflow UI.
8. Run Milestone 2 verification and update execution docs.
```

Replace `.Codex/tasks/current-tasks.md` with:

```markdown
# Current tasks

- [ ] Task 1: Add item-level Research Run schemas.
  - Verification: `D:\Hcworkspace\Anoconda3\envs\research_agent\python.exe -m pytest tests/test_research_run_service.py::test_research_run_model_defaults_to_no_paper_items tests/test_research_run_service.py::test_research_run_paper_item_tracks_item_lifecycle -q`
  - Completion note:
- [ ] Task 2: Add Zotero collection intake service.
  - Verification: `D:\Hcworkspace\Anoconda3\envs\research_agent\python.exe -m pytest tests/test_zotero_intake.py -q`
  - Completion note:
- [ ] Task 3: Add local paper processing service.
  - Verification: `D:\Hcworkspace\Anoconda3\envs\research_agent\python.exe -m pytest tests/test_paper_processing_service.py -q`
  - Completion note:
- [ ] Task 4: Update Knowledge Pack summary, trace, and tool calls.
  - Verification: `D:\Hcworkspace\Anoconda3\envs\research_agent\python.exe -m pytest tests/test_research_run_service.py::test_knowledge_pack_update_rewrites_summary_with_paper_counts tests/test_research_run_service.py::test_append_tool_call_record_writes_jsonl -q`
  - Completion note:
- [ ] Task 5: Orchestrate local collection execution.
  - Verification: `D:\Hcworkspace\Anoconda3\envs\research_agent\python.exe -m pytest tests/test_research_run_service.py tests/test_research_run_store.py -q`
  - Completion note:
- [ ] Task 6: Add API endpoint for local execution.
  - Verification: `D:\Hcworkspace\Anoconda3\envs\research_agent\python.exe -m pytest tests/test_research_run_router.py -q`
  - Completion note:
- [ ] Task 7: Update Streamlit Research Workflow UI.
  - Verification: `D:\Hcworkspace\Anoconda3\envs\research_agent\python.exe -m pytest tests/test_research_workflow_ui_import.py -q`
  - Completion note:
- [ ] Task 8: Run Milestone 2 verification and update execution docs.
  - Verification: `D:\Hcworkspace\Anoconda3\envs\research_agent\python.exe -m pytest tests/test_research_run_service.py tests/test_research_run_store.py tests/test_research_run_router.py tests/test_research_workflow_ui_import.py tests/test_zotero_intake.py tests/test_paper_processing_service.py -q`
  - Completion note:
```

- [ ] **Step 2: Run focused Milestone 2 tests**

Run:

```powershell
& 'D:\Hcworkspace\Anoconda3\envs\research_agent\python.exe' -m pytest tests/test_research_run_service.py tests/test_research_run_store.py tests/test_research_run_router.py tests/test_research_workflow_ui_import.py tests/test_zotero_intake.py tests/test_paper_processing_service.py -q
```

Expected: PASS.

- [ ] **Step 3: Run compatibility tests**

Run:

```powershell
& 'D:\Hcworkspace\Anoconda3\envs\research_agent\python.exe' -m pytest tests/test_pdf_parser.py tests/test_chunker.py tests/test_embedding_client_aliases.py tests/test_vector_store_metadata.py tests/test_note_generator.py -q
```

Expected: PASS. These ensure the local processing service still matches parser/chunker/vector/note assumptions.

- [ ] **Step 4: Inspect diff**

Run:

```powershell
git diff --stat
git diff --check
git status --short
```

Expected:

- No whitespace errors from `git diff --check`, aside from possible LF/CRLF warnings.
- Only Milestone 2 files and current plan/task tracker changed.
- Unrelated untracked `.codex/` and `third_party/` remain unstaged unless the user explicitly asks otherwise.

- [ ] **Step 5: Commit Task 8**

Run:

```powershell
git add .Codex/plans/current-plan.md .Codex/tasks/current-tasks.md
git commit -m "docs: update milestone 2 execution tracker"
```

## Full Milestone 2 Acceptance Check

Run:

```powershell
& 'D:\Hcworkspace\Anoconda3\envs\research_agent\python.exe' -m pytest tests/test_research_run_service.py tests/test_research_run_store.py tests/test_research_run_router.py tests/test_research_workflow_ui_import.py tests/test_zotero_intake.py tests/test_paper_processing_service.py tests/test_pdf_parser.py tests/test_chunker.py tests/test_embedding_client_aliases.py tests/test_vector_store_metadata.py tests/test_note_generator.py -q
```

Expected: PASS.

Then run:

```powershell
git log --oneline -8
git status --short
```

Expected:

- Recent commits include all Milestone 2 task commits.
- No Milestone 2 changes remain unstaged.
- Unrelated `.codex/` and `third_party/` may remain untracked if they were present before execution.

## Manual Smoke Flow

Use this after automated tests pass.

1. Start Zotero Desktop and ensure local API is enabled.
2. Start the backend:

```powershell
& 'D:\Hcworkspace\Anoconda3\envs\research_agent\python.exe' -m uvicorn app.main:app --reload
```

3. Start Streamlit in a second terminal:

```powershell
& 'D:\Hcworkspace\Anoconda3\envs\research_agent\python.exe' -m streamlit run ui/streamlit_app.py
```

4. Open `http://127.0.0.1:8501`.
5. Go to `Research Workflow`.
6. Enter a Zotero collection id/name and `Max papers = 3`.
7. Click `Initialize Research Run`.
8. Select the new run and click `Process Local Collection`.
9. Confirm the UI shows:

- Per-item status.
- Zotero item id.
- Paper id for completed papers.
- PDF path.
- Error for missing PDFs.
- Knowledge Pack artifact paths.

10. Confirm files exist under the run output directory:

- `00 Run Summary.md`
- `papers/*.md`
- `assets/trace.json`
- `assets/tool-calls.jsonl`

Do not record the final video in this implementation step. The user will handle final screen recording independently.

## Self-Review Checklist

- Milestone 2 acceptance criteria are covered by Tasks 1-8.
- Zotero intake can be tested without live Zotero by using fake clients.
- External MCP, Semantic Scholar, arXiv, and Obsidian publishing are excluded from this plan.
- Item failures continue processing remaining items.
- `.env` is not modified.
- No recursive delete commands are needed.
- The plan keeps M2 as a standalone demo milestone.
