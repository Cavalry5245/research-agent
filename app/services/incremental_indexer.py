from __future__ import annotations

import hashlib
import logging
from typing import Iterable

from app.schemas import Chunk

logger = logging.getLogger(__name__)


def _content_hash(chunk: Chunk) -> str:
    return hashlib.sha1(chunk.content.encode("utf-8")).hexdigest()


class IncrementalIndexer:
    def __init__(self, vector_store, embedding_client):
        self._vector_store = vector_store
        self._embedding = embedding_client

    def _existing_hashes(self, paper_id: str) -> dict[str, str]:
        existing = self._vector_store.list_chunks(paper_id=paper_id)
        return {
            c["chunk_id"]: hashlib.sha1((c.get("content") or "").encode("utf-8")).hexdigest()
            for c in existing
        }

    def update_paper_index(self, paper_id: str, new_chunks: Iterable[Chunk]) -> dict:
        new_list = list(new_chunks)
        new_hashes = {c.chunk_id: _content_hash(c) for c in new_list}
        old_hashes = self._existing_hashes(paper_id)

        to_remove_ids = [cid for cid in old_hashes if cid not in new_hashes]
        to_add = [c for c in new_list if old_hashes.get(c.chunk_id) != new_hashes[c.chunk_id]]
        unchanged = len(new_list) - len(to_add)

        if to_remove_ids:
            self._vector_store.delete_chunks(to_remove_ids)

        added = 0
        if to_add:
            embeddings = self._embedding.embed_texts([c.content for c in to_add])
            added = self._vector_store.add_chunks(to_add, embeddings)

        logger.info(
            "Incremental index for %s: +%d / -%d / =%d (unchanged)",
            paper_id, added, len(to_remove_ids), unchanged,
        )
        return {
            "paper_id": paper_id,
            "added": added,
            "removed": len(to_remove_ids),
            "unchanged": unchanged,
        }
