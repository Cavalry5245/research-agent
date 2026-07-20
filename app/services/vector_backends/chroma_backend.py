from __future__ import annotations

import hashlib
import os
import threading
import time
from contextlib import contextmanager
from typing import Any, BinaryIO, Iterator

import chromadb

from app.schemas import Chunk
from app.services.vector_backends.base import (
    VectorBackend,
    normalize_embeddings,
    normalize_vector,
)


_CHUNK_METADATA_FIELDS = (
    "paper_id",
    "title",
    "section",
    "page_number",
    "chunk_start",
    "chunk_end",
    "parent_id",
    "section_path",
    "page_range",
    "element_type",
)
_METADATA_LOCK_TIMEOUT_SECONDS = 10.0
_LOCAL_LOCKS: dict[str, threading.Lock] = {}
_LOCAL_LOCKS_GUARD = threading.Lock()


def _local_lock(path: str) -> threading.Lock:
    with _LOCAL_LOCKS_GUARD:
        return _LOCAL_LOCKS.setdefault(path, threading.Lock())


def _try_file_lock(handle: BinaryIO) -> bool:
    handle.seek(0)
    if os.name == "nt":
        import msvcrt

        try:
            msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
        except OSError:
            return False
        return True

    import fcntl

    try:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        return False
    return True


def _release_file_lock(handle: BinaryIO) -> None:
    handle.seek(0)
    if os.name == "nt":
        import msvcrt

        msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
        return

    import fcntl

    fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


@contextmanager
def _metadata_write_lock(
    persist_dir: str, collection_name: str
) -> Iterator[None]:
    digest = hashlib.sha256(collection_name.encode("utf-8")).hexdigest()[:16]
    lock_path = os.path.abspath(
        os.path.join(persist_dir, f".chroma-metadata-{digest}.lock")
    )
    local_lock = _local_lock(lock_path)
    if not local_lock.acquire(timeout=_METADATA_LOCK_TIMEOUT_SECONDS):
        raise TimeoutError(f"Timed out locking Chroma metadata for {collection_name!r}")

    handle: BinaryIO | None = None
    file_locked = False
    try:
        handle = open(lock_path, "a+b")
        handle.seek(0, os.SEEK_END)
        if handle.tell() == 0:
            handle.write(b"\0")
            handle.flush()

        deadline = time.monotonic() + _METADATA_LOCK_TIMEOUT_SECONDS
        while not _try_file_lock(handle):
            if time.monotonic() >= deadline:
                raise TimeoutError(
                    f"Timed out locking Chroma metadata for {collection_name!r}"
                )
            time.sleep(0.01)
        file_locked = True
        yield
    finally:
        try:
            if handle is not None:
                try:
                    if file_locked:
                        _release_file_lock(handle)
                finally:
                    handle.close()
        finally:
            local_lock.release()


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
        self.persist_dir = persist_dir
        self.collection_name = collection_name
        self._client = chromadb.PersistentClient(path=persist_dir)
        if create_if_missing:
            create_kwargs: dict[str, Any] = {
                "name": collection_name,
                "configuration": {"hnsw": {"space": "cosine"}},
                "embedding_function": None,
            }
            if initial_metadata:
                create_kwargs["metadata"] = initial_metadata
            self._collection = self._client.get_or_create_collection(**create_kwargs)
        else:
            self._collection = self._client.get_collection(
                name=collection_name,
                embedding_function=None,
            )

        self._validate_collection_contract(require_ready=require_ready)

    def _refresh_collection(self):
        self._collection = self._client.get_collection(
            name=self.collection_name,
            embedding_function=None,
        )
        return self._collection

    def _validate_collection_contract(self, *, require_ready: bool) -> None:
        space = (self._collection.configuration_json.get("hnsw") or {}).get("space")
        if space != "cosine":
            raise RuntimeError(
                f"Chroma collection {self.collection_name!r} must use cosine "
                f"HNSW space (found {space!r})"
            )

        collection_metadata = self._collection.metadata or {}
        if require_ready and collection_metadata.get("build_status") != "ready":
            raise RuntimeError(
                f"Chroma collection {self.collection_name!r} is not ready "
                f"(build_status={collection_metadata.get('build_status')!r})"
            )

        value = collection_metadata.get("embedding_dimension")
        if value is None:
            if (
                collection_metadata.get("build_status") == "ready"
                or self.count() > 0
            ):
                raise RuntimeError(
                    f"Chroma collection {self.collection_name!r} has no valid "
                    "embedding_dimension"
                )
        elif type(value) is not int or value <= 0:
            raise RuntimeError(
                f"Chroma collection {self.collection_name!r} has invalid "
                f"embedding_dimension={value!r}; expected a positive integer"
            )

    def _collection_metadata(self, *, refresh: bool = False) -> dict:
        if refresh:
            self._refresh_collection()
        return dict(self._collection.metadata or {})

    def _expected_dimension(
        self,
        *,
        chunk_count: int | None = None,
        refresh: bool = True,
    ) -> int | None:
        if refresh:
            self._refresh_collection()
        metadata = self._collection_metadata()
        value = metadata.get("embedding_dimension")
        if value is None:
            if (self.count() if chunk_count is None else chunk_count) > 0:
                raise RuntimeError(
                    f"Chroma collection {self.collection_name!r} has no valid "
                    "embedding_dimension"
                )
            return None
        if type(value) is not int or value <= 0:
            raise RuntimeError(
                f"Chroma collection {self.collection_name!r} has invalid "
                f"embedding_dimension={value!r}; expected a positive integer"
            )
        return value

    @staticmethod
    def _chunk_metadata(chunk: Chunk) -> dict:
        return {
            field: value
            for field in _CHUNK_METADATA_FIELDS
            if (value := getattr(chunk, field)) is not None
        }

    def add_chunks(self, chunks: list[Chunk], embeddings: list[list[float]]) -> int:
        expected_dimension = self._expected_dimension()
        normalized, dimension = normalize_embeddings(
            chunks,
            embeddings,
            expected_dimension=expected_dimension,
        )
        if not chunks:
            return 0

        # Chroma rejects duplicate IDs within one request. Preserve the shared
        # backend contract by retaining the final occurrence of each ID.
        rows = {
            chunk.chunk_id: (chunk, embedding)
            for chunk, embedding in zip(chunks, normalized)
        }
        self._collection.upsert(
            ids=list(rows),
            documents=[chunk.content for chunk, _ in rows.values()],
            metadatas=[self._chunk_metadata(chunk) for chunk, _ in rows.values()],
            embeddings=[embedding for _, embedding in rows.values()],
        )
        if expected_dimension is None and dimension is not None:
            self.update_build_metadata({"embedding_dimension": dimension})
        return len(chunks)

    def query_dense(
        self,
        query_embedding: list[float],
        top_k: int = 5,
        paper_id: str | None = None,
    ) -> list[dict]:
        normalized = normalize_vector(query_embedding, label="query embedding")
        self._refresh_collection()
        chunk_count = self.count()
        expected_dimension = self._expected_dimension(
            chunk_count=chunk_count,
            refresh=False,
        )
        if expected_dimension is not None and len(normalized) != expected_dimension:
            raise ValueError(
                f"query embedding dimension {len(normalized)} does not match "
                f"expected dimension {expected_dimension}"
            )
        if top_k <= 0 or chunk_count == 0:
            return []

        kwargs: dict[str, Any] = {
            "query_embeddings": [normalized],
            "n_results": min(top_k, chunk_count),
            "include": ["documents", "metadatas", "distances"],
        }
        if paper_id is not None:
            kwargs["where"] = {"paper_id": paper_id}
        result = self._collection.query(**kwargs)

        ids = (result.get("ids") or [[]])[0]
        documents = (result.get("documents") or [[]])[0]
        metadatas = (result.get("metadatas") or [[]])[0]
        distances = (result.get("distances") or [[]])[0]
        output = []
        for chunk_id, content, metadata, distance in zip(
            ids, documents, metadatas, distances
        ):
            item_metadata = metadata or {}
            output.append(
                {
                    "chunk_id": chunk_id,
                    "content": content,
                    "paper_id": item_metadata.get("paper_id"),
                    "title": item_metadata.get("title"),
                    "section": item_metadata.get("section"),
                    "page_number": item_metadata.get("page_number"),
                    "chunk_start": item_metadata.get("chunk_start"),
                    "chunk_end": item_metadata.get("chunk_end"),
                    "score": 1.0 - float(distance),
                    "parent_id": item_metadata.get("parent_id"),
                    "section_path": item_metadata.get("section_path"),
                    "page_range": item_metadata.get("page_range"),
                    "element_type": item_metadata.get("element_type"),
                }
            )
        return output

    def ids_for_paper(self, paper_id: str) -> set[str]:
        result = self._collection.get(where={"paper_id": paper_id}, include=[])
        return set(result.get("ids") or [])

    def delete_paper(self, paper_id: str) -> int:
        ids = self.ids_for_paper(paper_id)
        if not ids:
            return 0
        self._collection.delete(ids=sorted(ids))
        return len(ids)

    def delete_chunks(self, chunk_ids: list[str]) -> int:
        if not chunk_ids:
            return 0
        requested = sorted(set(chunk_ids))
        existing = set(
            self._collection.get(ids=requested, include=[]).get("ids") or []
        )
        if not existing:
            return 0
        self._collection.delete(ids=sorted(existing))
        return len(existing)

    def has_paper(self, paper_id: str) -> bool:
        return bool(self.ids_for_paper(paper_id))

    def backend_name(self) -> str:
        return "chroma"

    def metadata(self) -> dict:
        collection_metadata = self._collection_metadata(refresh=True)
        chunk_count = self.count()
        paper_ids: set[str] = set()
        offset = 0
        page_size = 1000
        while offset < chunk_count:
            result = self._collection.get(
                limit=page_size,
                offset=offset,
                include=["metadatas"],
            )
            ids = result.get("ids") or []
            if not ids:
                break
            for metadata in result.get("metadatas") or []:
                paper_id = (metadata or {}).get("paper_id")
                if paper_id is not None:
                    paper_ids.add(paper_id)
            offset += len(ids)
        return {
            "backend": self.backend_name(),
            "collection_name": self.collection_name,
            "build_status": collection_metadata.get("build_status"),
            "embedding_dimension": collection_metadata.get(
                "embedding_dimension"
            ),
            "chunk_count": chunk_count,
            "paper_count": len(paper_ids),
            "persist_dir": self.persist_dir,
        }

    def update_build_metadata(self, values: dict) -> None:
        with _metadata_write_lock(self.persist_dir, self.collection_name):
            collection = self._refresh_collection()
            merged = dict(collection.metadata or {})
            merged.update(values)
            collection.modify(metadata=merged)
            self._refresh_collection()

    def count(self) -> int:
        return self._collection.count()

    def list_chunks(self, paper_id: str | None = None) -> list[dict]:
        total = self.count()
        if total == 0:
            return []

        output = []
        offset = 0
        page_size = 1000
        while offset < total:
            kwargs: dict[str, Any] = {
                "limit": page_size,
                "offset": offset,
                "include": ["documents", "metadatas", "embeddings"],
            }
            if paper_id is not None:
                kwargs["where"] = {"paper_id": paper_id}
            result = self._collection.get(**kwargs)
            ids = result.get("ids") or []
            if not ids:
                break
            documents = result.get("documents") or []
            metadatas = result.get("metadatas") or []
            embeddings = result.get("embeddings")
            for index, chunk_id in enumerate(ids):
                metadata = metadatas[index] or {}
                embedding = embeddings[index] if embeddings is not None else []
                output.append(
                    {
                        "chunk_id": chunk_id,
                        "paper_id": metadata.get("paper_id"),
                        "title": metadata.get("title"),
                        "section": metadata.get("section"),
                        "content": documents[index],
                        "embedding_dim": len(embedding),
                    }
                )
            offset += len(ids)
        return sorted(output, key=lambda item: item["chunk_id"])
