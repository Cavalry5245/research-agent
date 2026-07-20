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

    try:
        finite = all(
            isfinite(float(value)) for vector in embeddings for value in vector
        )
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError("embeddings must contain only finite numeric values") from exc
    if not finite:
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
