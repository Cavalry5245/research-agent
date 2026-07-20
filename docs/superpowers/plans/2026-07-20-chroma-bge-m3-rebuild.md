# Chroma + bge-m3 Vector Index Rebuild Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the configuration-only Chroma claim with a real Chroma 1.5.9 backend and rebuild a validated, resumable cosine index for all 53 parsed papers using the configured OpenAI-compatible `bge-m3` API.

**Architecture:** Keep `app.services.vector_store.VectorStore` as the public facade, move the current JSON implementation behind a backend contract, and add a fail-fast Chroma backend selected by configuration. Build a versioned staging collection through a manifest-backed rebuild service and CLI, validate it before activation, and preserve the old JSON file as an explicit operational fallback.

**Tech Stack:** Python 3.11, Pydantic Settings, OpenAI-compatible embeddings API, ChromaDB 1.5.9 `PersistentClient`, Pytest.

---

## Scope and file map

Create:

- `app/services/vector_backends/__init__.py` — backend exports.
- `app/services/vector_backends/base.py` — backend protocol and shared embedding validation.
- `app/services/vector_backends/json_backend.py` — extracted JSON persistence and exact cosine search.
- `app/services/vector_backends/chroma_backend.py` — Chroma persistence, filtering, conversion, and readiness checks.
- `app/services/chroma_rebuild.py` — source discovery, manifest, retries, canary, resume, and verification.
- `scripts/rebuild_chroma_index.py` — command-line entry point.
- `tests/test_vector_backend_contract.py` — shared JSON/Chroma behavioral contract.
- `tests/test_vector_store_factory.py` — facade selection and fail-fast behavior.
- `tests/test_chroma_rebuild.py` — deterministic rebuild tests with fake embeddings.

Modify:

- `app/config.py` — collection and rebuild settings.
- `app/services/vector_store.py` — facade and shared hybrid rerank only.
- `requirements.txt` — pin Chroma 1.5.9.
- `.env.example` — document collection selection.
- Existing direct `VectorStore` unit tests — explicitly select JSON where the test is about legacy behavior.
- `tests/test_system_status_endpoint.py` and `tests/test_health_endpoint.py` — Chroma readiness metadata.
- `project-dossier/README.md`, `project-dossier/evidence_index.md`, `project-dossier/00_project_overview.md`, `project-dossier/03_core_modules.md`, and `project-dossier/05_decisions_and_tradeoffs.md` — update C1 only after live validation.

Do not modify or delete:

- `app/storage/vector_db/vector_store.json`.
- Existing Chroma collections with a different contract.
- PDFs, parsed JSON, parent documents, notes, evaluation reports, or unrelated working-tree changes.

Use `D:\Hcworkspace\Anoconda3\envs\research_agent\python.exe` for every Python and Pytest command; each task below provides the complete command line.

### Task 1: Lock configuration and dependency contracts

**Files:**

- Modify: `app/config.py:20-23`
- Modify: `requirements.txt:8`
- Modify: `.env.example`
- Create: `tests/test_vector_store_factory.py`

- [x] **Step 1: Add a failing configuration test**

Create `tests/test_vector_store_factory.py` with:

```python
from app.config import Settings


def test_vector_store_settings_have_versioned_chroma_collection():
    configured = Settings(
        _env_file=None,
        vector_store="chroma",
        chroma_persist_dir="tmp/chroma",
        chroma_collection_name="research_papers_bge_m3_v1",
    )

    assert configured.vector_store == "chroma"
    assert configured.chroma_persist_dir == "tmp/chroma"
    assert configured.chroma_collection_name == "research_papers_bge_m3_v1"
```

- [x] **Step 2: Run the test and confirm the missing field**

Run:

```powershell
& "D:\Hcworkspace\Anoconda3\envs\research_agent\python.exe" -m pytest tests/test_vector_store_factory.py::test_vector_store_settings_have_versioned_chroma_collection -v
```

Expected: FAIL because `Settings` has no `chroma_collection_name` field.

- [x] **Step 3: Add the minimal settings**

Add these fields under the vector-store block in `app/config.py`:

```python
    vector_store: str = "chroma"
    chroma_persist_dir: str = "app/storage/vector_db"
    chroma_collection_name: str = "research_papers_bge_m3_v1"
    chroma_require_ready: bool = True
```

Replace the unbounded `chromadb` entry in `requirements.txt` with:

```text
chromadb==1.5.9
```

Add to `.env.example` beside the vector-store settings:

```text
VECTOR_STORE=chroma
CHROMA_PERSIST_DIR=app/storage/vector_db
CHROMA_COLLECTION_NAME=research_papers_bge_m3_v1
CHROMA_REQUIRE_READY=true
```

- [x] **Step 4: Run the configuration test**

Run the Step 2 command.

Expected: PASS.

- [x] **Step 5: Inspect the diff and commit**

Run:

```powershell
git diff -- app/config.py requirements.txt .env.example tests/test_vector_store_factory.py
git add app/config.py requirements.txt .env.example tests/test_vector_store_factory.py
git commit -m "config: define versioned Chroma collection"
```

Expected: the commit contains only settings, the dependency pin, environment documentation, and the new test.

Completion note (2026-07-20): implemented in `750827ab`; strengthened the default contract test in `a93411e`. RED failed on the missing collection field; GREEN passed with 2 focused tests. Independent spec and quality reviews approved with no remaining Critical or Important issues.

### Task 2: Extract a strict JSON backend behind a common contract

**Files:**

- Create: `app/services/vector_backends/__init__.py`
- Create: `app/services/vector_backends/base.py`
- Create: `app/services/vector_backends/json_backend.py`
- Create: `tests/test_vector_backend_contract.py`
- Modify: `app/services/vector_store.py:1-196`

- [x] **Step 1: Write failing backend validation tests**

Create `tests/test_vector_backend_contract.py` with the JSON cases first:

```python
from pathlib import Path

import pytest

from app.schemas import Chunk
from app.services.vector_backends.json_backend import JsonVectorBackend


def _chunk(chunk_id: str, paper_id: str, content: str) -> Chunk:
    return Chunk(
        chunk_id=chunk_id,
        paper_id=paper_id,
        title=f"Title {paper_id}",
        section="Methods",
        content=content,
        page_number=2,
        chunk_start=0,
        chunk_end=len(content),
        parent_id=f"{paper_id}_parent",
        section_path="Methods/Setup",
        page_range="2-3",
        element_type="section",
    )


def test_json_backend_rejects_chunk_embedding_count_mismatch(tmp_path: Path):
    backend = JsonVectorBackend(str(tmp_path))

    with pytest.raises(ValueError, match="chunks and embeddings"):
        backend.add_chunks([_chunk("c1", "p1", "alpha")], [])


def test_json_backend_rejects_embedding_dimension_mismatch(tmp_path: Path):
    backend = JsonVectorBackend(str(tmp_path))
    backend.add_chunks([_chunk("c1", "p1", "alpha")], [[1.0, 0.0]])

    with pytest.raises(ValueError, match="dimension"):
        backend.add_chunks([_chunk("c2", "p2", "beta")], [[1.0, 0.0, 0.0]])


def test_json_backend_returns_complete_dense_result(tmp_path: Path):
    backend = JsonVectorBackend(str(tmp_path))
    backend.add_chunks([_chunk("c1", "p1", "alpha")], [[1.0, 0.0]])

    result = backend.query_dense([1.0, 0.0], top_k=1, paper_id="p1")[0]

    assert result == {
        "chunk_id": "c1",
        "content": "alpha",
        "paper_id": "p1",
        "title": "Title p1",
        "section": "Methods",
        "page_number": 2,
        "chunk_start": 0,
        "chunk_end": 5,
        "score": 1.0,
        "parent_id": "p1_parent",
        "section_path": "Methods/Setup",
        "page_range": "2-3",
        "element_type": "section",
    }
```

- [x] **Step 2: Run the tests and confirm the backend modules are absent**

Run:

```powershell
& "D:\Hcworkspace\Anoconda3\envs\research_agent\python.exe" -m pytest tests/test_vector_backend_contract.py -v
```

Expected: collection ERROR because `app.services.vector_backends` does not exist.

- [x] **Step 3: Define the backend contract and shared validation**

Create `app/services/vector_backends/base.py` with this public contract:

```python
from __future__ import annotations

from abc import ABC, abstractmethod
from math import isfinite
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.schemas import Chunk


def validate_embeddings(
    chunks: list[Chunk],
    embeddings: list[list[float]],
    *,
    expected_dimension: int | None = None,
) -> int | None:
    if len(chunks) != len(embeddings):
        raise ValueError("chunks and embeddings must have the same length")
    if not embeddings:
        return expected_dimension
    dimensions = {len(vector) for vector in embeddings}
    if 0 in dimensions or len(dimensions) != 1:
        raise ValueError("all embeddings must have one non-zero dimension")
    dimension = dimensions.pop()
    if expected_dimension is not None and dimension != expected_dimension:
        raise ValueError(
            f"embedding dimension {dimension} does not match expected dimension "
            f"{expected_dimension}"
        )
    if any(not isfinite(float(value)) for vector in embeddings for value in vector):
        raise ValueError("embeddings must contain only finite numeric values")
    return dimension


class VectorBackend(ABC):
    @abstractmethod
    def add_chunks(self, chunks: list[Chunk], embeddings: list[list[float]]) -> int:
        raise NotImplementedError

    @abstractmethod
    def query_dense(
        self,
        query_embedding: list[float],
        top_k: int = 5,
        paper_id: str | None = None,
    ) -> list[dict]:
        raise NotImplementedError

    @abstractmethod
    def delete_paper(self, paper_id: str) -> int:
        raise NotImplementedError

    @abstractmethod
    def delete_chunks(self, chunk_ids: list[str]) -> int:
        raise NotImplementedError

    @abstractmethod
    def has_paper(self, paper_id: str) -> bool:
        raise NotImplementedError

    @abstractmethod
    def backend_name(self) -> str:
        raise NotImplementedError

    @abstractmethod
    def metadata(self) -> dict:
        raise NotImplementedError

    @abstractmethod
    def count(self) -> int:
        raise NotImplementedError

    @abstractmethod
    def list_chunks(self, paper_id: str | None = None) -> list[dict]:
        raise NotImplementedError
```

- [x] **Step 4: Extract the JSON implementation**

Create `app/services/vector_backends/json_backend.py`. Move the current JSON load/persist logic into `JsonVectorBackend(VectorBackend)`, rename `query` to `query_dense`, remove hybrid reranking, and apply strict dimension checks:

```python
class JsonVectorBackend(VectorBackend):
    def __init__(self, persist_dir: str):
        self.persist_dir = persist_dir
        os.makedirs(self.persist_dir, exist_ok=True)
        self._store_path = os.path.join(self.persist_dir, STORE_FILENAME)
        self._store: list[tuple[str, Chunk, list[float]]] = []
        self._dimension: int | None = None
        self._dimensions: list[int] = []
        self._load()

    def _load(self) -> None:
        if not os.path.isfile(self._store_path):
            return
        with open(self._store_path, "r", encoding="utf-8") as handle:
            records = json.load(handle)
        loaded = []
        dimensions = set()
        for record in records:
            chunk = Chunk(**record["chunk"])
            embedding = [float(value) for value in record["embedding"]]
            dimensions.add(len(embedding))
            loaded.append((chunk.chunk_id, chunk, embedding))
        self._store = loaded
        self._dimensions = sorted(dimensions)
        self._dimension = self._dimensions[0] if len(self._dimensions) == 1 else None

    def add_chunks(self, chunks: list[Chunk], embeddings: list[list[float]]) -> int:
        dimension = validate_embeddings(
            chunks, embeddings, expected_dimension=self._dimension
        )
        if not chunks:
            return 0
        if self._store and self._dimension is None:
            raise ValueError(
                "JSON vector store contains mixed embedding dimensions; rebuild it "
                "before adding new chunks"
            )
        self._dimension = dimension
        self._dimensions = [dimension] if dimension is not None else []
        replacement_ids = {chunk.chunk_id for chunk in chunks}
        self._store = [row for row in self._store if row[0] not in replacement_ids]
        self._store.extend(
            (chunk.chunk_id, chunk, embedding)
            for chunk, embedding in zip(chunks, embeddings)
        )
        self._persist()
        return len(chunks)

    def query_dense(
        self,
        query_embedding: list[float],
        top_k: int = 5,
        paper_id: str | None = None,
    ) -> list[dict]:
        candidates = [
            (chunk_id, chunk, embedding)
            for chunk_id, chunk, embedding in self._store
            if paper_id is None or chunk.paper_id == paper_id
        ]
        candidate_dimensions = {len(embedding) for _, _, embedding in candidates}
        if candidate_dimensions and candidate_dimensions != {len(query_embedding)}:
            raise ValueError(
                "query embedding dimension does not match JSON candidate dimensions: "
                f"query={len(query_embedding)}, candidates={sorted(candidate_dimensions)}"
            )
        scored = sorted(
            (
                (_cosine_similarity(query_embedding, embedding), chunk_id, chunk)
                for chunk_id, chunk, embedding in candidates
            ),
            key=lambda row: -row[0],
        )[:top_k]
        return [_result_dict(score, chunk_id, chunk) for score, chunk_id, chunk in scored]
```

Retain the current implementations of `_persist`, `delete_paper`, `delete_chunks`, `has_paper`, `count`, and `list_chunks`, changing only `backend_name()` to return `"json"`. `metadata()` must additionally return `embedding_dimension` and `mixed_dimensions` so the legacy file reports its current unsafe state instead of hiding it.

Export `VectorBackend` and `JsonVectorBackend` from `app/services/vector_backends/__init__.py`.

- [x] **Step 5: Make `VectorStore` a temporary JSON facade**

Replace storage logic in `app/services/vector_store.py` with delegation while preserving shared reranking:

```python
class VectorStore:
    def __init__(self, persist_dir: str | None = None, backend=None):
        self.persist_dir = persist_dir or settings.chroma_persist_dir
        self._backend = backend or JsonVectorBackend(self.persist_dir)

    def add_chunks(self, chunks, embeddings):
        return self._backend.add_chunks(chunks, embeddings)

    def query(self, query_embedding, top_k=5, paper_id=None, hybrid_query_text=None):
        output = self._backend.query_dense(query_embedding, top_k, paper_id)
        if hybrid_query_text and output:
            output = HybridReranker().rerank(
                question=hybrid_query_text, results=output, top_k=top_k
            )
            for item in output:
                item["score"] = item.get("rerank_score", item.get("score", 0.0))
        return output

    def __getattr__(self, name):
        return getattr(self._backend, name)
```

Use explicit forwarding methods instead of `__getattr__` before committing if static type checking or tests require method discovery; the required public names are `delete_paper`, `delete_chunks`, `has_paper`, `backend_name`, `metadata`, `count`, and `list_chunks`.

- [x] **Step 6: Run legacy and new JSON tests**

Run:

```powershell
& "D:\Hcworkspace\Anoconda3\envs\research_agent\python.exe" -m pytest tests/test_vector_backend_contract.py tests/test_retrieval.py tests/test_vector_store_metadata.py tests/test_indexing_workflow.py -v
```

Expected: PASS. If the real project `.env` changes test selection, construct `JsonVectorBackend` explicitly in tests instead of weakening production configuration.

- [x] **Step 7: Inspect and commit**

Run:

```powershell
git diff -- app/services/vector_store.py app/services/vector_backends tests/test_vector_backend_contract.py
git add app/services/vector_store.py app/services/vector_backends tests/test_vector_backend_contract.py
git commit -m "refactor: extract JSON vector backend"
```

Expected: the application still uses JSON at this checkpoint and all existing behavior tests pass, except invalid mixed-dimension operations now fail clearly.

Completion note (2026-07-20): implemented in `949d5fa4`, hardened validation/degraded loading/atomic persistence in `6e7179f6`, and made mutations transactional in `1d36ef5e`. RED covered missing modules, duplicate IDs, invalid vectors, corrupt stores, and injected persistence failures. Final backend contract: 27 passed; independent spec and quality reviews approved with no remaining Critical or Important issues.

### Task 3: Add configuration-driven facade selection

**Files:**

- Modify: `app/services/vector_store.py`
- Modify: `tests/test_vector_store_factory.py`
- Modify direct-store tests: `tests/test_retrieval.py`, `tests/test_vector_store_metadata.py`, `tests/test_indexing_workflow.py`, `tests/test_paper_qa.py`, `tests/test_parent_backfill.py`, `tests/test_paper_status.py`, `tests/test_reranker.py`, `tests/test_paper_qa_closed_client.py`, `tests/test_index_endpoint.py`

- [x] **Step 1: Write failing facade-selection tests**

Append to `tests/test_vector_store_factory.py`:

```python
from unittest.mock import Mock, patch

import pytest

from app.services.vector_store import VectorStore


def test_vector_store_uses_explicit_backend_instance(tmp_path):
    backend = Mock()
    backend.backend_name.return_value = "stub"

    store = VectorStore(persist_dir=str(tmp_path), backend=backend)

    assert store.backend_name() == "stub"


def test_vector_store_rejects_unknown_configured_backend(tmp_path):
    with patch("app.services.vector_store.settings.vector_store", "unknown"):
        with pytest.raises(ValueError, match="Unsupported vector store backend"):
            VectorStore(persist_dir=str(tmp_path))


def test_vector_store_selects_json_from_configuration(tmp_path):
    with patch("app.services.vector_store.settings.vector_store", "json"):
        store = VectorStore(persist_dir=str(tmp_path))

    assert store.backend_name() == "json"
```

- [x] **Step 2: Run the factory tests and confirm failure**

Run:

```powershell
& "D:\Hcworkspace\Anoconda3\envs\research_agent\python.exe" -m pytest tests/test_vector_store_factory.py -v
```

Expected: unknown-backend and configured-selection tests FAIL because the facade still always creates JSON.

- [x] **Step 3: Implement strict selection**

Add a private factory in `app/services/vector_store.py`:

```python
def _create_backend(name: str, persist_dir: str):
    normalized = name.strip().lower()
    if normalized == "json":
        return JsonVectorBackend(persist_dir)
    if normalized == "chroma":
        from app.services.vector_backends.chroma_backend import ChromaVectorBackend

        return ChromaVectorBackend(
            persist_dir=persist_dir,
            collection_name=settings.chroma_collection_name,
            require_ready=settings.chroma_require_ready,
        )
    raise ValueError(f"Unsupported vector store backend: {name}")


class VectorStore:
    def __init__(self, persist_dir: str | None = None, backend=None):
        self.persist_dir = persist_dir or settings.chroma_persist_dir
        self._backend = backend or _create_backend(
            settings.vector_store, self.persist_dir
        )
```

Do not catch Chroma import, open, readiness, or dimension errors here.

- [x] **Step 4: Make JSON-focused tests explicit**

For each listed test file, replace JSON-specific construction:

```python
store = VectorStore(persist_dir=path)
```

with:

```python
store = VectorStore(
    persist_dir=path,
    backend=JsonVectorBackend(path),
)
```

Add `from app.services.vector_backends.json_backend import JsonVectorBackend` to those files. Do not change application call sites; they must continue using `VectorStore()` so configuration controls the real backend.

- [x] **Step 5: Run facade and affected tests**

Run:

```powershell
& "D:\Hcworkspace\Anoconda3\envs\research_agent\python.exe" -m pytest tests/test_vector_store_factory.py tests/test_retrieval.py tests/test_vector_store_metadata.py tests/test_indexing_workflow.py tests/test_paper_qa.py tests/test_parent_backfill.py tests/test_paper_status.py tests/test_reranker.py tests/test_paper_qa_closed_client.py tests/test_index_endpoint.py -v
```

Expected: factory tests pass; JSON behavior tests remain green without depending on `.env`.

- [x] **Step 6: Commit**

Run:

```powershell
git add app/services/vector_store.py tests/test_vector_store_factory.py tests/test_retrieval.py tests/test_vector_store_metadata.py tests/test_indexing_workflow.py tests/test_paper_qa.py tests/test_parent_backfill.py tests/test_paper_status.py tests/test_reranker.py tests/test_paper_qa_closed_client.py tests/test_index_endpoint.py
git commit -m "feat: select vector backend from configuration"
```

Completion note (2026-07-20): implemented in `bf5ff1e7`. Factory tests: 5 passed; affected offline suites: 97 passed with 2 explicit live embedding-client tests deselected; Task 2 contract/reranker/incremental suites: 39 passed. Independent spec and quality reviews approved with no issues.

### Task 4: Implement the Chroma backend

**Files:**

- Create: `app/services/vector_backends/chroma_backend.py`
- Modify: `app/services/vector_backends/__init__.py`
- Modify: `tests/test_vector_backend_contract.py`
- Modify: `tests/test_vector_store_factory.py`

- [x] **Step 1: Extend the shared contract tests to Chroma**

Add this fixture and parameterized core cases to `tests/test_vector_backend_contract.py`:

```python
from app.services.vector_backends.chroma_backend import ChromaVectorBackend


@pytest.fixture(params=["json", "chroma"])
def backend(request, tmp_path):
    if request.param == "json":
        return JsonVectorBackend(str(tmp_path / "json"))
    return ChromaVectorBackend(
        persist_dir=str(tmp_path / "chroma"),
        collection_name="test_research_papers",
        create_if_missing=True,
        require_ready=False,
        initial_metadata={
            "build_status": "building",
            "embedding_model": "fake",
            "embedding_dimension": 2,
            "schema_version": 1,
        },
    )


def test_backend_upsert_filter_delete_and_persistence(backend):
    chunks = [
        _chunk("c1", "p1", "alpha"),
        _chunk("c2", "p2", "beta"),
    ]
    backend.add_chunks(chunks, [[1.0, 0.0], [0.0, 1.0]])
    backend.add_chunks([chunks[0]], [[1.0, 0.0]])

    assert backend.count() == 2
    assert backend.has_paper("p1") is True
    assert [item["chunk_id"] for item in backend.list_chunks("p1")] == ["c1"]
    assert backend.query_dense([1.0, 0.0], top_k=1)[0]["chunk_id"] == "c1"
    assert backend.delete_chunks(["c2", "missing"]) == 1
    assert backend.delete_paper("p1") == 1
    assert backend.count() == 0


def test_chroma_backend_refuses_non_ready_collection(tmp_path):
    ChromaVectorBackend(
        persist_dir=str(tmp_path),
        collection_name="building_collection",
        create_if_missing=True,
        require_ready=False,
        initial_metadata={"build_status": "building", "schema_version": 1},
    )

    with pytest.raises(RuntimeError, match="not ready"):
        ChromaVectorBackend(
            persist_dir=str(tmp_path),
            collection_name="building_collection",
            require_ready=True,
        )
```

- [x] **Step 2: Run and confirm the Chroma module is absent**

Run:

```powershell
& "D:\Hcworkspace\Anoconda3\envs\research_agent\python.exe" -m pytest tests/test_vector_backend_contract.py -v
```

Expected: collection ERROR for the missing Chroma backend.

- [x] **Step 3: Implement metadata conversion helpers**

Create `app/services/vector_backends/chroma_backend.py` with helpers that omit `None` on write and restore optional fields on read:

```python
OPTIONAL_FIELDS = (
    "page_number",
    "chunk_start",
    "chunk_end",
    "parent_id",
    "section_path",
    "page_range",
    "element_type",
)


def _chunk_metadata(chunk: Chunk) -> dict:
    values = {
        "paper_id": chunk.paper_id,
        "title": chunk.title,
        "section": chunk.section,
        "page_number": chunk.page_number,
        "chunk_start": chunk.chunk_start,
        "chunk_end": chunk.chunk_end,
        "parent_id": chunk.parent_id,
        "section_path": chunk.section_path,
        "page_range": chunk.page_range,
        "element_type": chunk.element_type,
    }
    return {key: value for key, value in values.items() if value is not None}


def _query_result(
    chunk_id: str,
    document: str,
    metadata: dict,
    distance: float,
) -> dict:
    result = {
        "chunk_id": chunk_id,
        "content": document,
        "paper_id": metadata["paper_id"],
        "title": metadata.get("title", ""),
        "section": metadata.get("section", ""),
        "score": 1.0 - float(distance),
    }
    result.update({field: metadata.get(field) for field in OPTIONAL_FIELDS})
    return result
```

- [x] **Step 4: Implement open, readiness, and mutation operations**

Implement `ChromaVectorBackend(VectorBackend)` with these constructor semantics:

```python
class ChromaVectorBackend(VectorBackend):
    def __init__(
        self,
        *,
        persist_dir: str,
        collection_name: str,
        create_if_missing: bool = False,
        require_ready: bool = True,
        initial_metadata: dict | None = None,
    ):
        import chromadb

        self.persist_dir = persist_dir
        self.collection_name = collection_name
        self._client = chromadb.PersistentClient(path=persist_dir)
        if create_if_missing:
            self._collection = self._client.get_or_create_collection(
                name=collection_name,
                configuration={"hnsw": {"space": "cosine"}},
                metadata=initial_metadata or {},
                embedding_function=None,
            )
        else:
            self._collection = self._client.get_collection(
                name=collection_name,
                embedding_function=None,
            )
        if require_ready and self._collection.metadata.get("build_status") != "ready":
            raise RuntimeError(
                f"Chroma collection {collection_name!r} is not ready"
            )
```

Implement:

- `add_chunks` with `validate_embeddings`, collection `embedding_dimension`, and `upsert`;
- `query_dense` with `query_embeddings=[query_embedding]`, optional `where={"paper_id": paper_id}`, and `include=["documents", "metadatas", "distances"]`;
- `delete_paper` by first fetching IDs with the paper filter, then deleting those exact IDs;
- `delete_chunks` by fetching the requested IDs first and returning the number actually present;
- `has_paper`, `count`, and paginated `list_chunks`;
- `metadata` returning `backend`, `collection_name`, `build_status`, `embedding_dimension`, `chunk_count`, `paper_count`, and `persist_dir`;
- `ids_for_paper(paper_id)` returning the exact stored ID set for rebuild verification;
- `update_build_metadata(values)` that merges with existing collection metadata and calls `collection.modify(metadata=merged)`.

Do not let application code create a missing collection. Only the rebuild path passes `create_if_missing=True`.

- [x] **Step 5: Run contract and factory tests**

Run:

```powershell
& "D:\Hcworkspace\Anoconda3\envs\research_agent\python.exe" -m pytest tests/test_vector_backend_contract.py tests/test_vector_store_factory.py -v
```

Expected: JSON and Chroma contract cases pass, cosine score for an identical vector is approximately `1.0`, and a building collection is rejected by the application path.

- [x] **Step 6: Commit**

Run:

```powershell
git add app/services/vector_backends/chroma_backend.py app/services/vector_backends/__init__.py tests/test_vector_backend_contract.py tests/test_vector_store_factory.py
git commit -m "feat: add persistent Chroma vector backend"
```

Completion note (2026-07-20): implemented in `92365012`; fixed empty metadata creation in `12bc6d0b`; enforced distance/dimension/locking/efficient metadata contracts in `4590e019`; validated lifecycle metadata in `d237f1de`. Final real ChromaDB 1.5.9 contract/factory suite: 83 passed. Independent spec and quality reviews approved with no remaining Critical or Important issues.

### Task 5: Build manifest and source-validation primitives

**Files:**

- Create: `app/services/chroma_rebuild.py`
- Create: `tests/test_chroma_rebuild.py`

- [x] **Step 1: Write failing manifest tests**

Create `tests/test_chroma_rebuild.py`:

```python
import json
from pathlib import Path

import pytest

from app.services.chroma_rebuild import (
    discover_parsed_sources,
    load_manifest,
    redact_error,
    source_sha256,
    validate_resume_contract,
    write_manifest,
)


def test_discovery_is_sorted_and_hash_is_stable(tmp_path: Path):
    second = tmp_path / "paper_b_parsed.json"
    first = tmp_path / "paper_a_parsed.json"
    second.write_text('{"paper_id":"b"}', encoding="utf-8")
    first.write_text('{"paper_id":"a"}', encoding="utf-8")

    assert discover_parsed_sources(tmp_path) == [first, second]
    assert source_sha256(first) == source_sha256(first)


def test_manifest_write_is_utf8_and_round_trips(tmp_path: Path):
    path = tmp_path / "manifest.json"
    manifest = {"status": "building", "papers": {"论文": {"status": "completed"}}}

    write_manifest(path, manifest)

    assert load_manifest(path) == manifest
    assert json.loads(path.read_text(encoding="utf-8")) == manifest


def test_error_redaction_removes_credentials():
    message = "Authorization: Bearer secret-value api_key=secret-value sk-example"

    redacted = redact_error(message)

    assert "secret-value" not in redacted
    assert "sk-example" not in redacted
```

- [x] **Step 2: Run and confirm the rebuild module is absent**

Run:

```powershell
& "D:\Hcworkspace\Anoconda3\envs\research_agent\python.exe" -m pytest tests/test_chroma_rebuild.py -v
```

Expected: collection ERROR because `app.services.chroma_rebuild` does not exist.

- [x] **Step 3: Implement deterministic discovery and manifest I/O**

Create `app/services/chroma_rebuild.py` with:

```python
from __future__ import annotations

import hashlib
import json
import os
import re
from pathlib import Path


def discover_parsed_sources(metadata_dir: Path) -> list[Path]:
    return sorted(metadata_dir.glob("*_parsed.json"), key=lambda path: path.name)


def source_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load_manifest(path: Path) -> dict | None:
    if not path.is_file():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def write_manifest(path: Path, manifest: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    os.replace(temporary, path)


def redact_error(message: str) -> str:
    redacted = re.sub(
        r"(?i)(authorization\s*:\s*bearer|api[_-]?key\s*=)\s*[^\s,;]+",
        r"\1 [REDACTED]",
        message,
    )
    return re.sub(r"\bsk-[A-Za-z0-9_-]+", "[REDACTED]", redacted)
```

Add helpers that create a new manifest with collection contract, Git HEAD, chunk settings, relative source paths and hashes. Reject resume when collection, model, Git HEAD, schema version, or chunk settings differ. The error must name the mismatched fields without including credentials.

- [x] **Step 4: Add resume-contract tests**

Add tests that assert:

```python
def test_resume_rejects_changed_build_contract():
    existing = {
        "collection": "research_papers_bge_m3_v1",
        "model": "bge-m3",
        "git_head": "abc",
        "schema_version": 1,
        "chunk_settings": {"strategy": "parent_child_sliding_window", "size": 500, "overlap": 100},
    }
    requested = {**existing, "git_head": "def"}

    with pytest.raises(ValueError, match="git_head"):
        validate_resume_contract(existing, requested)
```

- [x] **Step 5: Run tests and commit**

Run:

```powershell
& "D:\Hcworkspace\Anoconda3\envs\research_agent\python.exe" -m pytest tests/test_chroma_rebuild.py -v
git add app/services/chroma_rebuild.py tests/test_chroma_rebuild.py
git commit -m "feat: add Chroma rebuild manifest primitives"
```

Expected: manifest and contract tests pass; the manifest contains no secret value.

Completion note (2026-07-20): implemented in `c06054b2`; hardened atomic persistence, strict contracts, path containment, and structured credential redaction in `a4e1ced3` and `6e0c3093`. Final Task 5 suite: 51 passed, 1 skipped because Windows symlink creation was unavailable; vector backend regressions: 83 passed. Independent spec and repeated quality reviews approved with no remaining Critical, Important, or Minor findings.

### Task 6: Implement canary, retries, full rebuild, and resume

**Files:**

- Modify: `app/services/chroma_rebuild.py`
- Modify: `tests/test_chroma_rebuild.py`
- Create: `scripts/rebuild_chroma_index.py`

- [ ] **Step 1: Write failing retry and resume tests**

Add fakes and tests to `tests/test_chroma_rebuild.py`:

```python
class RetryableEmbeddingError(RuntimeError):
    status_code = 429


class FakeEmbeddingClient:
    provider = "api"
    model_name = "bge-m3"

    def __init__(self, failures: int = 0):
        self.failures = failures
        self.calls = 0

    def embed_texts(self, texts):
        self.calls += 1
        if self.calls <= self.failures:
            raise RetryableEmbeddingError("rate limited")
        return [[float(index + 1), 0.0, 1.0] for index, _ in enumerate(texts)]


def test_embed_batch_retries_429_without_sleeping():
    client = FakeEmbeddingClient(failures=2)
    sleeps = []

    vectors = embed_batch_with_retry(
        client,
        ["a", "b"],
        max_attempts=3,
        base_delay=0.25,
        sleep=sleeps.append,
    )

    assert len(vectors) == 2
    assert client.calls == 3
    assert sleeps == [0.25, 0.5]


```

- [ ] **Step 2: Run and confirm missing behavior**

Run:

```powershell
& "D:\Hcworkspace\Anoconda3\envs\research_agent\python.exe" -m pytest tests/test_chroma_rebuild.py -v
```

Expected: FAIL because `embed_batch_with_retry` is not defined.

- [ ] **Step 3: Implement bounded embedding retries**

Add:

```python
import time
from collections.abc import Callable


def _retryable_embedding_error(exc: Exception) -> bool:
    status_code = getattr(exc, "status_code", None)
    return status_code == 429 or status_code in {500, 502, 503, 504} or isinstance(
        exc, TimeoutError
    )


def embed_batch_with_retry(
    client,
    texts: list[str],
    *,
    max_attempts: int,
    base_delay: float,
    sleep: Callable[[float], None] = time.sleep,
) -> list[list[float]]:
    for attempt in range(1, max_attempts + 1):
        try:
            return client.embed_texts(texts)
        except Exception as exc:
            if not _retryable_embedding_error(exc) or attempt == max_attempts:
                raise
            retry_after = getattr(exc, "retry_after", None)
            delay = float(retry_after) if retry_after is not None else base_delay * 2 ** (attempt - 1)
            sleep(delay)
    raise AssertionError("retry loop exited unexpectedly")
```

- [ ] **Step 4: Implement `ChromaIndexRebuilder`**

Add a class with this constructor and public operations:

```python
class ChromaIndexRebuilder:
    def __init__(
        self,
        *,
        metadata_dir: Path,
        manifest_path: Path,
        backend: ChromaVectorBackend,
        embedding_client,
        batch_size: int,
        max_attempts: int,
        base_delay: float,
        git_head: str,
        chunk_settings: dict,
        expected_source_count: int,
    ):
        self.metadata_dir = metadata_dir
        self.manifest_path = manifest_path
        self.backend = backend
        self.embedding_client = embedding_client
        self.batch_size = batch_size
        self.max_attempts = max_attempts
        self.base_delay = base_delay
        self.git_head = git_head
        self.chunk_settings = chunk_settings
        self.expected_source_count = expected_source_count

    def run_canary(self) -> dict:
        sources = self._validated_sources()
        canary = sorted(sources, key=lambda path: (path.stat().st_size, path.name))[
            len(sources) // 2
        ]
        self._process_source(canary)
        return self.verify(require_complete=False)

    def run_all(self) -> dict:
        sources = self._validated_sources()
        if not self._manifest_has_completed_paper():
            self.run_canary()
        for source in sources:
            if not self._should_skip(source):
                self._process_source(source)
        result = self.verify(require_complete=True)
        self._write_manifest_status("ready", result)
        self.backend.update_build_metadata({"build_status": "ready"})
        return {**result, "status": "ready"}

    def verify(self, *, require_complete: bool = True) -> dict:
        return self._verify_manifest_and_collection(require_complete=require_complete)
```

Implement the operations with these exact invariants:

1. Discover sorted sources and require exactly the requested source count supplied by the CLI; the production command supplies `53`.
2. Choose the canary deterministically as the median source by file size.
3. Parse each source with `PaperParseResult.model_validate_json` and call `chunk_paper(parsed)`.
4. Embed `chunk.content` in configured batches through `embed_batch_with_retry`.
5. Call `validate_embeddings` before any upsert; lock `embedding_dimension` from the first successful batch.
6. Upsert the complete paper, fetch its IDs by `paper_id`, and require exact ID-set equality.
7. Mark a paper completed only after equality succeeds.
8. Skip only when source hash, completed status, expected IDs, and Chroma IDs all match.
9. Store only redacted exception text in the manifest.
10. Set collection `build_status=ready` only when all expected sources are completed and `verify()` confirms paper count, chunk count, ID uniqueness, and dimension.

On a source hash change, delete only that paper's IDs from the staging collection immediately before its replacement upsert. This record-level deletion is scoped to the approved staging collection and must not remove files or collections.

- [ ] **Step 5: Write a full fake rebuild test**

Add imports and a real parsed-result fixture:

```python
from app.schemas import PaperParseResult, Section
from app.services.vector_backends.chroma_backend import ChromaVectorBackend


def _write_parsed_fixture(tmp_path: Path, paper_id: str) -> Path:
    parsed = PaperParseResult(
        paper_id=paper_id,
        title=f"Title {paper_id}",
        abstract=f"Abstract for {paper_id}",
        sections=[Section(heading="Methods", content="method details " * 80)],
        full_text=(f"Abstract for {paper_id}\n" + "method details " * 80),
    )
    path = tmp_path / f"{paper_id}_parsed.json"
    path.write_text(parsed.model_dump_json(), encoding="utf-8")
    return path
```

Then add the complete resume test:

```python
def test_rebuild_canary_full_run_and_no_cost_resume(tmp_path: Path):
    metadata_dir = tmp_path / "metadata"
    metadata_dir.mkdir()
    _write_parsed_fixture(metadata_dir, "paper_1")
    _write_parsed_fixture(metadata_dir, "paper_2")
    manifest_path = tmp_path / "rebuild_manifest.json"
    backend = ChromaVectorBackend(
        persist_dir=str(tmp_path / "chroma"),
        collection_name="rebuild_test",
        create_if_missing=True,
        require_ready=False,
        initial_metadata={
            "build_status": "building",
            "embedding_model": "bge-m3",
            "schema_version": 1,
        },
    )
    first_client = FakeEmbeddingClient()
    rebuilder = ChromaIndexRebuilder(
        metadata_dir=metadata_dir,
        manifest_path=manifest_path,
        backend=backend,
        embedding_client=first_client,
        batch_size=8,
        max_attempts=3,
        base_delay=0.01,
        git_head="test-head",
        chunk_settings={
            "strategy": "parent_child_sliding_window",
            "size": 500,
            "overlap": 100,
        },
        expected_source_count=2,
    )

    canary = rebuilder.run_canary()
    result = rebuilder.run_all()
    manifest = load_manifest(manifest_path)

    assert canary["completed_paper_count"] == 1
    assert result["status"] == "ready"
    assert result["paper_count"] == 2
    assert backend.count() == result["chunk_count"]
    assert manifest["papers"]["paper_1"]["status"] == "completed"
    assert manifest["papers"]["paper_2"]["status"] == "completed"

    second_client = FakeEmbeddingClient()
    resumed = ChromaIndexRebuilder(
        metadata_dir=metadata_dir,
        manifest_path=manifest_path,
        backend=backend,
        embedding_client=second_client,
        batch_size=8,
        max_attempts=3,
        base_delay=0.01,
        git_head="test-head",
        chunk_settings={
            "strategy": "parent_child_sliding_window",
            "size": 500,
            "overlap": 100,
        },
        expected_source_count=2,
    )

    resumed_result = resumed.run_all()

    assert resumed_result["status"] == "ready"
    assert second_client.calls == 0
```

- [ ] **Step 6: Add the CLI**

Create `scripts/rebuild_chroma_index.py` with arguments:

```python
parser.add_argument("--metadata-dir", default=settings.metadata_dir)
parser.add_argument("--persist-dir", default=settings.chroma_persist_dir)
parser.add_argument("--collection", default=settings.chroma_collection_name)
parser.add_argument("--expected-source-count", type=int, default=53)
parser.add_argument("--batch-size", type=int, default=settings.embedding_batch_size)
parser.add_argument("--max-attempts", type=int, default=5)
parser.add_argument("--base-delay", type=float, default=1.0)
parser.add_argument("--canary-only", action="store_true")
parser.add_argument("--verify-only", action="store_true")
```

The script must:

- validate `settings.embedding_provider == "api"` and `settings.embedding_model == "bge-m3"`;
- print only booleans for base URL/key presence;
- derive `git_head` via `git rev-parse HEAD`;
- open/create the staging backend with `require_ready=False`;
- run verify-only, canary-only, or canary-then-full according to arguments;
- return exit code 0 only on the requested successful terminal state.

- [ ] **Step 7: Run rebuild tests**

Run:

```powershell
& "D:\Hcworkspace\Anoconda3\envs\research_agent\python.exe" -m pytest tests/test_chroma_rebuild.py tests/test_vector_backend_contract.py -v
```

Expected: PASS without external network calls.

- [ ] **Step 8: Commit**

Run:

```powershell
git add app/services/chroma_rebuild.py scripts/rebuild_chroma_index.py tests/test_chroma_rebuild.py
git commit -m "feat: add resumable bge-m3 Chroma rebuild"
```

### Task 7: Expose readiness and protect application startup

**Files:**

- Modify: `app/main.py:199-256,1399-1417`
- Modify: `tests/test_health_endpoint.py`
- Modify: `tests/test_system_status_endpoint.py`
- Modify: `tests/test_agent_tools.py`

- [ ] **Step 1: Write failing readiness assertions**

Update the system-status stub metadata to include:

```python
return {
    "backend": "chroma",
    "collection_name": "research_papers_bge_m3_v1",
    "build_status": "ready",
    "embedding_dimension": 1024,
    "chunk_count": 100,
    "paper_count": 2,
    "persist_dir": "app/storage/vector_db",
}
```

Assert the endpoint returns those fields. Add a health test whose stub returns `build_status="building"` and assert the service is degraded rather than healthy.

- [ ] **Step 2: Run and confirm readiness is not enforced**

Run:

```powershell
& "D:\Hcworkspace\Anoconda3\envs\research_agent\python.exe" -m pytest tests/test_health_endpoint.py tests/test_system_status_endpoint.py tests/test_agent_tools.py -v
```

Expected: at least the building-status health assertion FAILS.

- [ ] **Step 3: Update health and system status**

Change vector availability to require a usable backend:

```python
vector_meta = _get_vector_store().metadata()
vector_store_available = vector_meta.get("backend") is not None and (
    vector_meta.get("backend") != "chroma"
    or vector_meta.get("build_status") == "ready"
)
```

Return the full safe metadata dict from system status. Do not expose API base URL or key. Preserve the existing degraded response when vector-store initialization raises.

- [ ] **Step 4: Run endpoint tests and a facade smoke test**

Run:

```powershell
& "D:\Hcworkspace\Anoconda3\envs\research_agent\python.exe" -m pytest tests/test_health_endpoint.py tests/test_system_status_endpoint.py tests/test_agent_tools.py tests/test_vector_store_factory.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

Run:

```powershell
git add app/main.py tests/test_health_endpoint.py tests/test_system_status_endpoint.py tests/test_agent_tools.py
git commit -m "feat: report Chroma collection readiness"
```

### Task 8: Run the real canary and 53-paper rebuild

**Files:**

- Runtime output only: `app/storage/vector_db/` Chroma files and rebuild manifest
- No source files should change during this task

- [ ] **Step 1: Verify secret-safe configuration**

Run:

```powershell
& "D:\Hcworkspace\Anoconda3\envs\research_agent\python.exe" -c "from app.config import settings; print({'provider': settings.embedding_provider, 'model': settings.embedding_model, 'base_url_configured': bool(settings.embedding_base_url), 'api_key_configured': bool(settings.embedding_api_key), 'collection': settings.chroma_collection_name})"
```

Expected: provider `api`, model `bge-m3`, both booleans `True`, and collection `research_papers_bge_m3_v1`. The key value must not appear.

- [ ] **Step 2: Run the canary only**

Run:

```powershell
& "D:\Hcworkspace\Anoconda3\envs\research_agent\python.exe" scripts/rebuild_chroma_index.py --canary-only --expected-source-count 53
```

Expected: one paper completes, actual embedding dimension is recorded, ID-set verification succeeds, collection remains `building`, and the command exits 0.

- [ ] **Step 3: Inspect canary state without printing secrets**

Run:

```powershell
& "D:\Hcworkspace\Anoconda3\envs\research_agent\python.exe" scripts/rebuild_chroma_index.py --verify-only --expected-source-count 53
```

Expected: verification reports one completed paper and `building`; it does not claim full readiness.

- [ ] **Step 4: Resume into the full rebuild**

Run:

```powershell
& "D:\Hcworkspace\Anoconda3\envs\research_agent\python.exe" scripts/rebuild_chroma_index.py --expected-source-count 53
```

Expected: the canary paper is skipped after hash/ID verification, the remaining 52 papers are processed, and final status is `ready`.

- [ ] **Step 5: Perform final collection verification**

Run:

```powershell
& "D:\Hcworkspace\Anoconda3\envs\research_agent\python.exe" scripts/rebuild_chroma_index.py --verify-only --expected-source-count 53
```

Expected: 53 completed papers, collection and manifest chunk totals match, IDs are unique, dimension is uniform, and status is `ready`.

- [ ] **Step 6: Confirm runtime files are not staged**

Run:

```powershell
git status --short
git check-ignore -v app/storage/vector_db/chroma.sqlite3
```

Expected: generated Chroma data and manifest are ignored or remain deliberately unstaged. Do not add database files or the manifest to Git.

### Task 9: Activate Chroma and run application smoke tests

**Files:**

- Local environment only: `.env`
- Test: existing application endpoint and retrieval tests

- [ ] **Step 1: Confirm activation configuration**

Ensure the local `.env` contains these non-secret selections:

```text
VECTOR_STORE=chroma
CHROMA_PERSIST_DIR=app/storage/vector_db
CHROMA_COLLECTION_NAME=research_papers_bge_m3_v1
CHROMA_REQUIRE_READY=true
EMBEDDING_PROVIDER=api
EMBEDDING_MODEL=bge-m3
```

Do not print or commit `.env`.

- [ ] **Step 2: Run a direct store smoke test**

Run:

```powershell
& "D:\Hcworkspace\Anoconda3\envs\research_agent\python.exe" -c "from app.services.vector_store import VectorStore; store=VectorStore(); meta=store.metadata(); print({k: meta.get(k) for k in ('backend','collection_name','build_status','embedding_dimension','chunk_count','paper_count')}); assert meta['backend']=='chroma'; assert meta['build_status']=='ready'; assert meta['paper_count']==53"
```

Expected: backend `chroma`, correct collection, ready status, one embedding dimension, and 53 papers.

- [ ] **Step 3: Run a real embedding retrieval smoke test**

Run a small script through `EmbeddingClient.embed_query` and `VectorStore.query` using a general research query. Print only chunk ID, paper ID, section, and score for the top three results. Assert three results are returned and all required result keys exist.

Expected: API query embedding dimension matches the collection and Chroma returns ranked results without fallback.

- [ ] **Step 4: Run endpoint smoke tests**

Run:

```powershell
& "D:\Hcworkspace\Anoconda3\envs\research_agent\python.exe" -m pytest tests/test_health_endpoint.py tests/test_system_status_endpoint.py tests/test_index_endpoint.py tests/test_paper_qa.py -v
```

Expected: PASS.

- [ ] **Step 5: Exercise explicit rollback without deleting data**

Temporarily set `VECTOR_STORE=json` in the process environment only and instantiate `VectorStore`. Assert `backend_name()=="json"` and inspect metadata. Restore the process environment after the command. Because the legacy JSON file has mixed dimensions, do not claim that arbitrary `bge-m3` queries can use it; the purpose of this check is to prove explicit backend selection and preserve the file for forensic rollback.

Expected: JSON backend opens and reports mixed dimensions clearly; no file or collection is removed.

### Task 10: Update project evidence and run final verification

**Files:**

- Modify: `project-dossier/README.md`
- Modify: `project-dossier/evidence_index.md`
- Modify: `project-dossier/00_project_overview.md`
- Modify: `project-dossier/03_core_modules.md`
- Modify: `project-dossier/05_decisions_and_tradeoffs.md`
- Modify: `docs/superpowers/plans/2026-07-20-chroma-bge-m3-rebuild.md` while executing, checking completed steps and adding concise completion notes

- [ ] **Step 1: Update C1 only with verified facts**

Change the dossier language from “JSON only / Chroma pending” to:

```text
向量存储采用统一门面和双后端：Chroma 1.5.9 为默认后端，使用 bge-m3 API
重建的版本化 cosine collection；JSON 后端保留为显式兼容/诊断路径。历史混合
维度 JSON 向量未迁移，新的 Chroma collection 由 53 份 parsed JSON 全量重算并通过
manifest、逐篇 ID 回读和维度一致性校验。
```

Record actual runtime evidence from Task 8: collection name, paper count, chunk count, embedding dimension, and verification date. Do not invent any value before reading it from the ready collection.

- [ ] **Step 2: Run focused vector and rebuild tests**

Run:

```powershell
& "D:\Hcworkspace\Anoconda3\envs\research_agent\python.exe" -m pytest tests/test_vector_backend_contract.py tests/test_vector_store_factory.py tests/test_chroma_rebuild.py tests/test_retrieval.py tests/test_vector_store_metadata.py tests/test_indexing_workflow.py tests/test_health_endpoint.py tests/test_system_status_endpoint.py -v
```

Expected: PASS.

- [ ] **Step 3: Run the full non-performance suite**

Run:

```powershell
& "D:\Hcworkspace\Anoconda3\envs\research_agent\python.exe" -m pytest tests -v --ignore=tests/performance
```

Expected: PASS with no collection errors, hangs, secret-bearing error output, or unexpected network calls in unit tests.

- [ ] **Step 4: Inspect all source changes and runtime state**

Run:

```powershell
git diff --check
git status --short
git diff --stat
```

Expected: no whitespace errors; existing unrelated changes remain untouched; Chroma runtime files are not staged.

- [ ] **Step 5: Commit verified documentation and any final test-only adjustments**

Run:

```powershell
git add project-dossier/README.md project-dossier/evidence_index.md project-dossier/00_project_overview.md project-dossier/03_core_modules.md project-dossier/05_decisions_and_tradeoffs.md docs/superpowers/plans/2026-07-20-chroma-bge-m3-rebuild.md
git commit -m "docs: record verified Chroma index rollout"
```

Expected: only verified documentation, the checked-off plan, and deliberate final test adjustments are committed. Existing unrelated files remain unstaged.

## Completion criteria

Implementation is complete only when all of the following are true:

- `VectorStore()` honors `VECTOR_STORE` and does not silently fall back.
- Chroma opens only an existing ready collection on the application path.
- JSON and Chroma satisfy the shared backend contract.
- `research_papers_bge_m3_v1` contains all 53 parsed papers with one actual embedding dimension.
- Manifest and collection chunk totals and ID sets agree.
- A real `bge-m3` query returns complete result records.
- Targeted tests and the full non-performance suite pass.
- No API key appears in logs, manifests, test output, commits, or documentation.
- The old `vector_store.json` and all unrelated working-tree files remain preserved.
