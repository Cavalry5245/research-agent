from __future__ import annotations

from app.config import settings
from app.schemas import Chunk
from app.services.reranker import HybridReranker
from app.services.vector_backends import JsonVectorBackend, VectorBackend


def _create_backend(name: str, persist_dir: str) -> VectorBackend:
    normalized = name.strip().lower()
    if normalized == "json":
        return JsonVectorBackend(persist_dir)
    if normalized == "chroma":
        from app.services.vector_backends.chroma_backend import ChromaVectorBackend

        return ChromaVectorBackend(
            persist_dir=persist_dir,
            collection_name=settings.chroma_collection_name,
            require_ready=settings.chroma_require_ready,
            expected_contract={
                "embedding_provider": settings.embedding_provider,
                "embedding_model": settings.embedding_model,
                "schema_version": settings.chroma_schema_version,
                "chunk_strategy": settings.chunk_strategy,
                "chunk_size": settings.child_chunk_size,
                "chunk_overlap": settings.child_chunk_overlap,
                "source_count": settings.chroma_expected_source_count,
            },
        )
    raise ValueError(f"Unsupported vector store backend: {name}")


class VectorStore:
    def __init__(
        self,
        persist_dir: str | None = None,
        backend: VectorBackend | None = None,
    ):
        self.persist_dir = persist_dir or settings.chroma_persist_dir
        self._backend = (
            backend
            if backend is not None
            else _create_backend(settings.vector_store, self.persist_dir)
        )

    def add_chunks(self, chunks: list[Chunk], embeddings: list[list[float]]) -> int:
        return self._backend.add_chunks(chunks, embeddings)

    def query(
        self,
        query_embedding: list[float],
        top_k: int = 5,
        paper_id: str | None = None,
        hybrid_query_text: str | None = None,
    ) -> list[dict]:
        output = self._backend.query_dense(query_embedding, top_k, paper_id)
        if hybrid_query_text and output:
            output = HybridReranker().rerank(
                question=hybrid_query_text, results=output, top_k=top_k
            )
            for item in output:
                item["score"] = item.get("rerank_score", item.get("score", 0.0))
        return output

    def delete_paper(self, paper_id: str) -> int:
        return self._backend.delete_paper(paper_id)

    def delete_chunks(self, chunk_ids: list[str]) -> int:
        return self._backend.delete_chunks(chunk_ids)

    def has_paper(self, paper_id: str) -> bool:
        return self._backend.has_paper(paper_id)

    def backend_name(self) -> str:
        return self._backend.backend_name()

    def metadata(self) -> dict:
        return self._backend.metadata()

    def count(self) -> int:
        return self._backend.count()

    def list_chunks(self, paper_id: str | None = None) -> list[dict]:
        return self._backend.list_chunks(paper_id)
