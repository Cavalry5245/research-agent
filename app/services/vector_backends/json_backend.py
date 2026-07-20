from __future__ import annotations

import json
import logging
import math
import os

from app.schemas import Chunk
from app.services.vector_backends.base import VectorBackend, validate_embeddings

logger = logging.getLogger(__name__)

STORE_FILENAME = "vector_store.json"


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(x * x for x in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


def _result_dict(score: float, chunk_id: str, chunk: Chunk) -> dict:
    return {
        "chunk_id": chunk_id,
        "content": chunk.content,
        "paper_id": chunk.paper_id,
        "title": chunk.title,
        "section": chunk.section,
        "page_number": chunk.page_number,
        "chunk_start": chunk.chunk_start,
        "chunk_end": chunk.chunk_end,
        "score": score,
        "parent_id": chunk.parent_id,
        "section_path": chunk.section_path,
        "page_range": chunk.page_range,
        "element_type": chunk.element_type,
    }


class JsonVectorBackend(VectorBackend):
    def __init__(self, persist_dir: str):
        self.persist_dir = persist_dir
        os.makedirs(self.persist_dir, exist_ok=True)
        self._store_path = os.path.join(self.persist_dir, STORE_FILENAME)
        self._store: list[tuple[str, Chunk, list[float]]] = []
        self._dimension: int | None = None
        self._dimensions: list[int] = []
        self._load()

    def _refresh_dimensions(self) -> None:
        self._dimensions = sorted({len(embedding) for _, _, embedding in self._store})
        self._dimension = self._dimensions[0] if len(self._dimensions) == 1 else None

    def _load(self) -> None:
        if not os.path.isfile(self._store_path):
            return
        try:
            with open(self._store_path, "r", encoding="utf-8") as handle:
                records = json.load(handle)
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            logger.warning(
                "Failed to load vector store from %s: %s", self._store_path, exc
            )
            return

        if not isinstance(records, list):
            logger.warning("Skipping invalid vector store payload: expected a list")
            return

        loaded: list[tuple[str, Chunk, list[float]]] = []
        for record in records:
            try:
                chunk = Chunk(**record["chunk"])
                embedding = [float(value) for value in record["embedding"]]
                loaded.append((chunk.chunk_id, chunk, embedding))
            except (KeyError, TypeError, ValueError, OverflowError) as exc:
                logger.warning("Skipping invalid vector store record: %s", exc)
        self._store = loaded
        self._refresh_dimensions()
        logger.info("Loaded %d chunks from vector store", len(self._store))

    def _persist(self) -> None:
        records = [
            {
                "chunk_id": chunk_id,
                "chunk": chunk.model_dump(),
                "embedding": embedding,
            }
            for chunk_id, chunk, embedding in self._store
        ]
        with open(self._store_path, "w", encoding="utf-8") as handle:
            json.dump(records, handle, ensure_ascii=False)

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

        replacement_ids = {chunk.chunk_id for chunk in chunks}
        self._store = [row for row in self._store if row[0] not in replacement_ids]
        replacements = {
            chunk.chunk_id: (chunk.chunk_id, chunk, embedding)
            for chunk, embedding in zip(chunks, embeddings)
        }
        self._store.extend(replacements.values())
        self._dimension = dimension
        self._dimensions = [dimension] if dimension is not None else []
        self._persist()
        logger.info("Added %d chunks to vector store", len(chunks))
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
        candidate_dimensions = {
            len(embedding) for _, _, embedding in candidates
        }
        if candidate_dimensions and candidate_dimensions != {len(query_embedding)}:
            raise ValueError(
                "query embedding dimension does not match JSON candidate dimensions: "
                f"query={len(query_embedding)}, "
                f"candidates={sorted(candidate_dimensions)}"
            )

        scored = sorted(
            (
                (_cosine_similarity(query_embedding, embedding), chunk_id, chunk)
                for chunk_id, chunk, embedding in candidates
            ),
            key=lambda row: -row[0],
        )[:top_k]
        output = [
            _result_dict(score, chunk_id, chunk)
            for score, chunk_id, chunk in scored
        ]
        logger.info("Query returned %d results (paper_id=%s)", len(output), paper_id)
        return output

    def delete_paper(self, paper_id: str) -> int:
        before = len(self._store)
        self._store = [
            (chunk_id, chunk, embedding)
            for chunk_id, chunk, embedding in self._store
            if chunk.paper_id != paper_id
        ]
        deleted = before - len(self._store)
        if deleted:
            self._refresh_dimensions()
            self._persist()
        logger.info("Deleted %d chunks for paper %s", deleted, paper_id)
        return deleted

    def delete_chunks(self, chunk_ids: list[str]) -> int:
        if not chunk_ids:
            return 0
        target = set(chunk_ids)
        before = len(self._store)
        self._store = [row for row in self._store if row[0] not in target]
        deleted = before - len(self._store)
        if deleted:
            self._refresh_dimensions()
            self._persist()
        return deleted

    def has_paper(self, paper_id: str) -> bool:
        return any(chunk.paper_id == paper_id for _, chunk, _ in self._store)

    def backend_name(self) -> str:
        return "json"

    def metadata(self) -> dict:
        paper_count = len({chunk.paper_id for _, chunk, _ in self._store})
        return {
            "backend": self.backend_name(),
            "chunk_count": len(self._store),
            "paper_count": paper_count,
            "store_path": self._store_path,
            "persist_dir": self.persist_dir,
            "embedding_dimension": self._dimension,
            "mixed_dimensions": list(self._dimensions),
        }

    def count(self) -> int:
        return len(self._store)

    def list_chunks(self, paper_id: str | None = None) -> list[dict]:
        output = []
        for chunk_id, chunk, embedding in self._store:
            if paper_id and chunk.paper_id != paper_id:
                continue
            output.append(
                {
                    "chunk_id": chunk_id,
                    "paper_id": chunk.paper_id,
                    "title": chunk.title,
                    "section": chunk.section,
                    "content": chunk.content,
                    "embedding_dim": len(embedding),
                }
            )
        return output
