import json
import os
from pathlib import Path

import pytest

from app.schemas import Chunk
from app.services.vector_backends.json_backend import JsonVectorBackend


@pytest.fixture(params=["json", "chroma"])
def backend(request, tmp_path: Path):
    if request.param == "json":
        return JsonVectorBackend(str(tmp_path / "json"))

    from app.services.vector_backends.chroma_backend import ChromaVectorBackend

    return ChromaVectorBackend(
        persist_dir=str(tmp_path / "chroma"),
        collection_name="test_research_papers",
        create_if_missing=True,
        require_ready=False,
        initial_metadata={
            "build_status": "building",
            "embedding_model": "fake",
            "embedding_dimension": 2,
            "schema_version": 1,
        },
    )


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


def test_backend_rejects_chunk_embedding_count_mismatch(backend):
    with pytest.raises(ValueError, match="chunks and embeddings"):
        backend.add_chunks([_chunk("c1", "p1", "alpha")], [])


def test_backend_rejects_embedding_dimension_mismatch(backend):
    backend.add_chunks([_chunk("c1", "p1", "alpha")], [[1.0, 0.0]])

    with pytest.raises(ValueError, match="dimension"):
        backend.add_chunks([_chunk("c2", "p2", "beta")], [[1.0, 0.0, 0.0]])


def test_backend_returns_complete_dense_result(backend):
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


def test_backend_upserts_same_id_and_ranks_globally_with_filter(backend):
    backend.add_chunks(
        [_chunk("c1", "p1", "old"), _chunk("c2", "p2", "beta")],
        [[1.0, 0.0], [0.0, 1.0]],
    )
    backend.add_chunks([_chunk("c1", "p1", "new")], [[0.8, 0.2]])

    assert backend.count() == 2
    assert backend.has_paper("p1") is True
    assert backend.has_paper("missing") is False
    assert [row["chunk_id"] for row in backend.query_dense([1.0, 0.0], 2)] == [
        "c1",
        "c2",
    ]
    assert [
        row["chunk_id"]
        for row in backend.query_dense([0.0, 1.0], 2, paper_id="p1")
    ] == ["c1"]
    assert backend.list_chunks("p1") == [
        {
            "chunk_id": "c1",
            "paper_id": "p1",
            "title": "Title p1",
            "section": "Methods",
            "content": "new",
            "embedding_dim": 2,
        }
    ]


def test_backend_deletes_only_existing_chunks_and_paper(backend):
    backend.add_chunks(
        [
            _chunk("c1", "p1", "alpha"),
            _chunk("c2", "p1", "beta"),
            _chunk("c3", "p2", "gamma"),
        ],
        [[1.0, 0.0], [0.5, 0.5], [0.0, 1.0]],
    )

    assert backend.delete_chunks(["c1", "missing", "c1"]) == 1
    assert backend.delete_chunks([]) == 0
    assert backend.delete_paper("p1") == 1
    assert backend.delete_paper("missing") == 0
    assert [row["chunk_id"] for row in backend.list_chunks()] == ["c3"]


def test_backend_persists_across_reinstantiation(backend, tmp_path: Path, request):
    backend.add_chunks([_chunk("c1", "p1", "alpha")], [[1.0, 0.0]])

    if request.node.callspec.params["backend"] == "json":
        reopened = JsonVectorBackend(str(tmp_path / "json"))
    else:
        from app.services.vector_backends.chroma_backend import ChromaVectorBackend

        reopened = ChromaVectorBackend(
            persist_dir=str(tmp_path / "chroma"),
            collection_name="test_research_papers",
            require_ready=False,
        )

    assert reopened.count() == 1
    assert reopened.list_chunks()[0]["content"] == "alpha"


def test_chroma_ready_open_rejects_building_collection(tmp_path: Path):
    from app.services.vector_backends.chroma_backend import ChromaVectorBackend

    kwargs = {
        "persist_dir": str(tmp_path / "chroma"),
        "collection_name": "building_collection",
    }
    ChromaVectorBackend(
        **kwargs,
        create_if_missing=True,
        require_ready=False,
        initial_metadata={"build_status": "building", "embedding_dimension": 2},
    )

    with pytest.raises(RuntimeError, match="not ready"):
        ChromaVectorBackend(**kwargs, require_ready=True)


def test_chroma_sets_first_embedding_dimension_and_reports_metadata(tmp_path: Path):
    from app.services.vector_backends import ChromaVectorBackend

    backend = ChromaVectorBackend(
        persist_dir=str(tmp_path / "chroma"),
        collection_name="dimension_collection",
        create_if_missing=True,
        require_ready=False,
        initial_metadata={"build_status": "building"},
    )
    backend.add_chunks(
        [_chunk("c1", "p1", "alpha"), _chunk("c2", "p2", "beta")],
        [[1.0, 0.0], [0.0, 1.0]],
    )

    assert backend.ids_for_paper("p1") == {"c1"}
    assert backend.metadata() == {
        "backend": "chroma",
        "collection_name": "dimension_collection",
        "build_status": "building",
        "embedding_dimension": 2,
        "chunk_count": 2,
        "paper_count": 2,
        "persist_dir": str(tmp_path / "chroma"),
    }


def test_chroma_update_build_metadata_merges_existing_values(tmp_path: Path):
    from app.services.vector_backends.chroma_backend import ChromaVectorBackend

    backend = ChromaVectorBackend(
        persist_dir=str(tmp_path / "chroma"),
        collection_name="metadata_collection",
        create_if_missing=True,
        require_ready=False,
        initial_metadata={"build_status": "building", "schema_version": 1},
    )

    backend.update_build_metadata({"build_status": "ready"})

    assert backend._collection.metadata == {
        "build_status": "ready",
        "schema_version": 1,
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


@pytest.mark.parametrize(
    "invalid_vector",
    [
        pytest.param(["1.0", 0.0], id="string"),
        pytest.param([True, 0.0], id="bool"),
        pytest.param([float("nan"), 0.0], id="nan"),
        pytest.param([float("inf"), 0.0], id="infinity"),
        pytest.param([], id="empty"),
    ],
)
def test_backend_rejects_invalid_write_vector(backend, invalid_vector: list):
    with pytest.raises(ValueError, match="embedding"):
        backend.add_chunks([_chunk("c1", "p1", "alpha")], [invalid_vector])

    assert backend.count() == 0


@pytest.mark.parametrize(
    "invalid_query",
    [
        pytest.param(["1.0", 0.0], id="string"),
        pytest.param([True, 0.0], id="bool"),
        pytest.param([float("nan"), 0.0], id="nan"),
        pytest.param([float("-inf"), 0.0], id="infinity"),
        pytest.param([], id="empty"),
    ],
)
def test_backend_rejects_invalid_query_vector(backend, invalid_query: list):
    backend.add_chunks([_chunk("c1", "p1", "alpha")], [[1.0, 0.0]])

    with pytest.raises(ValueError, match="query embedding"):
        backend.query_dense(invalid_query)


def test_json_backend_skips_invalid_legacy_vectors(tmp_path: Path, caplog):
    valid = _chunk("valid", "p1", "valid")
    invalid = _chunk("invalid", "p1", "invalid")
    records = [
        {"chunk": valid.model_dump(), "embedding": [1, 0]},
        {"chunk": invalid.model_dump(), "embedding": []},
        {"chunk": invalid.model_dump(), "embedding": ["not-a-number", 0]},
        {"chunk": invalid.model_dump(), "embedding": [True, 0]},
        {"chunk": invalid.model_dump(), "embedding": [float("nan"), 0]},
        {"chunk": invalid.model_dump(), "embedding": [float("inf"), 0]},
    ]
    (tmp_path / "vector_store.json").write_text(
        json.dumps(records), encoding="utf-8"
    )

    backend = JsonVectorBackend(str(tmp_path))

    assert backend.count() == 1
    assert backend.list_chunks()[0]["chunk_id"] == "valid"
    assert backend.metadata()["embedding_dimension"] == 2
    assert "Skipping invalid vector store record" in caplog.text


@pytest.mark.parametrize(
    "payload",
    [
        pytest.param(b"{malformed", id="malformed-json"),
        pytest.param(b'{"records": []}', id="invalid-top-level"),
    ],
)
@pytest.mark.parametrize(
    "mutation",
    ["add_chunks", "delete_paper", "delete_chunks", "persist"],
)
def test_json_backend_degraded_load_preserves_original_file(
    tmp_path: Path, payload: bytes, mutation: str
):
    store_path = tmp_path / "vector_store.json"
    store_path.write_bytes(payload)
    backend = JsonVectorBackend(str(tmp_path))

    assert backend.metadata()["load_failed"] is True
    assert backend.metadata()["degraded"] is True

    with pytest.raises(RuntimeError, match="load failed"):
        if mutation == "add_chunks":
            backend.add_chunks([_chunk("c1", "p1", "alpha")], [[1.0, 0.0]])
        elif mutation == "delete_paper":
            backend.delete_paper("p1")
        elif mutation == "delete_chunks":
            backend.delete_chunks(["c1"])
        else:
            backend._persist()

    assert store_path.read_bytes() == payload


def test_json_backend_persists_atomically_and_reloads(
    tmp_path: Path, monkeypatch
):
    replace_calls: list[tuple[Path, Path]] = []
    real_replace = os.replace

    def recording_replace(source, destination):
        replace_calls.append((Path(source), Path(destination)))
        real_replace(source, destination)

    monkeypatch.setattr(
        "app.services.vector_backends.json_backend.os.replace", recording_replace
    )
    backend = JsonVectorBackend(str(tmp_path))

    backend.add_chunks([_chunk("c1", "p1", "alpha")], [[1, 0]])

    assert len(replace_calls) == 1
    temporary, destination = replace_calls[0]
    assert temporary.parent == tmp_path
    assert destination == tmp_path / "vector_store.json"
    assert temporary.exists() is False
    reloaded = JsonVectorBackend(str(tmp_path))
    assert reloaded.count() == 1
    assert reloaded.list_chunks()[0]["chunk_id"] == "c1"


def _backend_snapshot(backend: JsonVectorBackend, store_path: Path) -> tuple:
    return (
        store_path.read_bytes(),
        backend.count(),
        backend.list_chunks(),
        backend.metadata(),
    )


def _raise_replace_error(*_args) -> None:
    raise OSError("injected replace failure")


def test_failed_add_is_transactional_and_does_not_leak_later(
    tmp_path: Path, monkeypatch
):
    store_path = tmp_path / "vector_store.json"
    backend = JsonVectorBackend(str(tmp_path))
    backend.add_chunks([_chunk("c1", "p1", "alpha")], [[1.0, 0.0]])
    before = _backend_snapshot(backend, store_path)

    with monkeypatch.context() as context:
        context.setattr(
            "app.services.vector_backends.json_backend.os.replace",
            _raise_replace_error,
        )
        with pytest.raises(OSError, match="injected replace failure"):
            backend.add_chunks([_chunk("c2", "p2", "beta")], [[0.0, 1.0]])

    assert _backend_snapshot(backend, store_path) == before
    assert list(tmp_path.glob(".vector_store.json.*.tmp")) == []

    backend.add_chunks([_chunk("c3", "p3", "gamma")], [[1.0, 1.0]])
    reloaded = JsonVectorBackend(str(tmp_path))
    assert {item["chunk_id"] for item in reloaded.list_chunks()} == {"c1", "c3"}


def test_failed_delete_paper_is_transactional_and_does_not_leak_later(
    tmp_path: Path, monkeypatch
):
    store_path = tmp_path / "vector_store.json"
    backend = JsonVectorBackend(str(tmp_path))
    backend.add_chunks(
        [_chunk("c1", "p1", "alpha"), _chunk("c2", "p2", "beta")],
        [[1.0, 0.0], [0.0, 1.0]],
    )
    before = _backend_snapshot(backend, store_path)

    with monkeypatch.context() as context:
        context.setattr(
            "app.services.vector_backends.json_backend.os.replace",
            _raise_replace_error,
        )
        with pytest.raises(OSError, match="injected replace failure"):
            backend.delete_paper("p1")

    assert _backend_snapshot(backend, store_path) == before
    assert list(tmp_path.glob(".vector_store.json.*.tmp")) == []

    backend.delete_paper("p2")
    reloaded = JsonVectorBackend(str(tmp_path))
    assert [item["chunk_id"] for item in reloaded.list_chunks()] == ["c1"]


def test_failed_delete_chunks_is_transactional_and_does_not_leak_later(
    tmp_path: Path, monkeypatch
):
    store_path = tmp_path / "vector_store.json"
    backend = JsonVectorBackend(str(tmp_path))
    backend.add_chunks(
        [_chunk("c1", "p1", "alpha"), _chunk("c2", "p1", "beta")],
        [[1.0, 0.0], [0.0, 1.0]],
    )
    before = _backend_snapshot(backend, store_path)

    with monkeypatch.context() as context:
        context.setattr(
            "app.services.vector_backends.json_backend.os.replace",
            _raise_replace_error,
        )
        with pytest.raises(OSError, match="injected replace failure"):
            backend.delete_chunks(["c1"])

    assert _backend_snapshot(backend, store_path) == before
    assert list(tmp_path.glob(".vector_store.json.*.tmp")) == []

    backend.delete_chunks(["c2"])
    reloaded = JsonVectorBackend(str(tmp_path))
    assert [item["chunk_id"] for item in reloaded.list_chunks()] == ["c1"]
