import json
import logging
import math
import os
from typing import TYPE_CHECKING

from app.config import settings

if TYPE_CHECKING:
    from app.schemas import Chunk

logger = logging.getLogger(__name__)

COLLECTION_NAME = "research_papers"
STORE_FILENAME = "vector_store.json"


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(x * x for x in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


class VectorStore:
    def __init__(self, persist_dir: str | None = None):
        self.persist_dir = persist_dir or settings.chroma_persist_dir
        os.makedirs(self.persist_dir, exist_ok=True)
        self._store_path = os.path.join(self.persist_dir, STORE_FILENAME)
        self._store: list[tuple[str, "Chunk", list[float]]] = []
        self._load()

    def _load(self) -> None:
        if not os.path.isfile(self._store_path):
            return
        try:
            with open(self._store_path, "r", encoding="utf-8") as f:
                records = json.load(f)
        except (OSError, json.JSONDecodeError) as e:
            logger.warning("Failed to load vector store from %s: %s", self._store_path, e)
            return

        from app.schemas import Chunk

        loaded: list[tuple[str, "Chunk", list[float]]] = []
        for record in records:
            try:
                chunk = Chunk(**record["chunk"])
                embedding = [float(x) for x in record["embedding"]]
                loaded.append((chunk.chunk_id, chunk, embedding))
            except (KeyError, TypeError, ValueError) as e:
                logger.warning("Skipping invalid vector store record: %s", e)
        self._store = loaded
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
        with open(self._store_path, "w", encoding="utf-8") as f:
            json.dump(records, f, ensure_ascii=False)

    def add_chunks(self, chunks: "list[Chunk]", embeddings: list[list[float]]) -> int:
        if not chunks:
            return 0
        for chunk, emb in zip(chunks, embeddings):
            self._store.append((chunk.chunk_id, chunk, emb))
        self._persist()
        logger.info("Added %d chunks to vector store", len(chunks))
        return len(chunks)

    def query(
        self,
        query_embedding: list[float],
        top_k: int = 5,
        paper_id: str | None = None,
    ) -> list[dict]:
        scored = []
        for chunk_id, chunk, emb in self._store:
            if paper_id and chunk.paper_id != paper_id:
                continue
            score = _cosine_similarity(query_embedding, emb)
            scored.append((score, chunk_id, chunk))

        scored.sort(key=lambda x: -x[0])
        top = scored[:top_k]

        output = []
        for score, cid, chunk in top:
            output.append({
                "chunk_id": cid,
                "content": chunk.content,
                "paper_id": chunk.paper_id,
                "title": chunk.title,
                "section": chunk.section,
                "score": score,
            })

        logger.info("Query returned %d results (paper_id=%s)", len(output), paper_id)
        return output

    def delete_paper(self, paper_id: str) -> int:
        before = len(self._store)
        self._store = [
            (cid, chunk, emb)
            for cid, chunk, emb in self._store
            if chunk.paper_id != paper_id
        ]
        deleted = before - len(self._store)
        if deleted:
            self._persist()
        logger.info("Deleted %d chunks for paper %s", deleted, paper_id)
        return deleted

    def count(self) -> int:
        return len(self._store)

    def list_chunks(self, paper_id: str | None = None) -> list[dict]:
        output = []
        for chunk_id, chunk, emb in self._store:
            if paper_id and chunk.paper_id != paper_id:
                continue
            output.append({
                "chunk_id": chunk_id,
                "paper_id": chunk.paper_id,
                "title": chunk.title,
                "section": chunk.section,
                "content": chunk.content,
                "embedding_dim": len(emb),
            })
        return output
