from typing import TYPE_CHECKING

from app.services.vector_backends.base import VectorBackend
from app.services.vector_backends.json_backend import JsonVectorBackend

if TYPE_CHECKING:
    from app.services.vector_backends.chroma_backend import ChromaVectorBackend

__all__ = ["ChromaVectorBackend", "JsonVectorBackend", "VectorBackend"]


def __getattr__(name: str):
    if name == "ChromaVectorBackend":
        from app.services.vector_backends.chroma_backend import ChromaVectorBackend

        return ChromaVectorBackend
    raise AttributeError(name)
