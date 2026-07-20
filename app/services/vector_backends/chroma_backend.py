from __future__ import annotations

from typing import Any

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

        collection_metadata = self._collection.metadata or {}
        if require_ready and collection_metadata.get("build_status") != "ready":
            raise RuntimeError(
                f"Chroma collection {collection_name!r} is not ready "
                f"(build_status={collection_metadata.get('build_status')!r})"
            )

    def _collection_metadata(self) -> dict:
        return dict(self._collection.metadata or {})

    def _expected_dimension(self) -> int | None:
        value = self._collection_metadata().get("embedding_dimension")
        return int(value) if value is not None else None

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
        expected_dimension = self._expected_dimension()
        if expected_dimension is not None and len(normalized) != expected_dimension:
            raise ValueError(
                f"query embedding dimension {len(normalized)} does not match "
                f"expected dimension {expected_dimension}"
            )
        if top_k <= 0 or self.count() == 0:
            return []

        kwargs: dict[str, Any] = {
            "query_embeddings": [normalized],
            "n_results": min(top_k, self.count()),
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
        collection_metadata = self._collection_metadata()
        chunks = self.list_chunks()
        return {
            "backend": self.backend_name(),
            "collection_name": self.collection_name,
            "build_status": collection_metadata.get("build_status"),
            "embedding_dimension": collection_metadata.get(
                "embedding_dimension"
            ),
            "chunk_count": len(chunks),
            "paper_count": len({chunk["paper_id"] for chunk in chunks}),
            "persist_dir": self.persist_dir,
        }

    def update_build_metadata(self, values: dict) -> None:
        merged = self._collection_metadata()
        merged.update(values)
        self._collection.modify(metadata=merged)

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
