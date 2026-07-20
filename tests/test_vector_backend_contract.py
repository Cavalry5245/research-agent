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


def test_json_backend_keeps_only_last_duplicate_id_in_batch(tmp_path: Path):
    backend = JsonVectorBackend(str(tmp_path))

    backend.add_chunks(
        [_chunk("c1", "p1", "alpha"), _chunk("c1", "p1", "beta")],
        [[1.0, 0.0], [0.0, 1.0]],
    )

    assert backend.count() == 1
    assert backend.list_chunks() == [
        {
            "chunk_id": "c1",
            "paper_id": "p1",
            "title": "Title p1",
            "section": "Methods",
            "content": "beta",
            "embedding_dim": 2,
        }
    ]
