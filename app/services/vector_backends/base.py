from __future__ import annotations

from abc import ABC, abstractmethod
from math import isfinite
from numbers import Real
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.schemas import Chunk


def normalize_vector(vector: list[float], *, label: str = "embedding") -> list[float]:
    if not isinstance(vector, (list, tuple)) or not vector:
        raise ValueError(f"{label} vector must have a non-empty dimension")
    if any(isinstance(value, bool) or not isinstance(value, Real) for value in vector):
        raise ValueError(f"{label} vector must contain only real numeric values")

    normalized = [float(value) for value in vector]
    if any(not isfinite(value) for value in normalized):
        raise ValueError(f"{label} vector must contain only finite real numeric values")
    return normalized


def normalize_embeddings(
    chunks: list[Chunk],
    embeddings: list[list[float]],
    *,
    expected_dimension: int | None = None,
) -> tuple[list[list[float]], int | None]:
    if len(chunks) != len(embeddings):
        raise ValueError("chunks and embeddings must have the same length")
    if not embeddings:
        return [], expected_dimension

    normalized = [normalize_vector(vector) for vector in embeddings]
    dimensions = {len(vector) for vector in normalized}
    if len(dimensions) != 1:
        raise ValueError("all embeddings must have one non-zero dimension")

    dimension = dimensions.pop()
    if expected_dimension is not None and dimension != expected_dimension:
        raise ValueError(
            f"embedding dimension {dimension} does not match expected dimension "
            f"{expected_dimension}"
        )

    return normalized, dimension


def validate_embeddings(
    chunks: list[Chunk],
    embeddings: list[list[float]],
    *,
    expected_dimension: int | None = None,
) -> int | None:
    _, dimension = normalize_embeddings(
        chunks, embeddings, expected_dimension=expected_dimension
    )
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
