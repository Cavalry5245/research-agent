import json
import os
import threading
from pathlib import Path
from unittest.mock import Mock

import chromadb
import pytest

from app.schemas import Chunk
from app.services.vector_backends.chroma_backend import (
    ChromaVectorBackend,
    validate_chroma_collection_name,
)
from app.services.vector_backends.json_backend import JsonVectorBackend


@pytest.fixture(params=["json", "chroma"])
def backend(request, tmp_path: Path):
    if request.param == "json":
        return JsonVectorBackend(str(tmp_path / "json"))

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


@pytest.mark.parametrize(
    "collection_name",
    [
        "abc",
        "A0._-z",
        "a" + ("x" * 61) + "z",
        "a" + ("x" * 62) + "z",
        "a" + ("x" * 510) + "z",
        "999.999.999.999",
    ],
)
def test_chroma_collection_name_validator_accepts_exact_valid_names(
    collection_name,
):
    assert validate_chroma_collection_name(collection_name) == collection_name


@pytest.mark.parametrize(
    "collection_name",
    [
        None,
        True,
        7,
        "",
        "ab",
        "a" * 513,
        "../escape",
        "a/b",
        r"a\b",
        "/absolute",
        r"C:\escape",
        ".abc",
        "abc.",
        "-abc",
        "abc-",
        "a b",
        "a@b",
        "论文abc",
        "ａｂｃ",
        "abc..def",
        "127.0.0.1",
    ],
)
def test_chroma_collection_name_validator_rejects_invalid_names(collection_name):
    with pytest.raises(ValueError, match="Chroma collection name"):
        validate_chroma_collection_name(collection_name)


@pytest.mark.parametrize(
    "collection_name",
    ["../escape", "论文abc", "a" * 513, "127.0.0.1"],
)
def test_chroma_backend_rejects_invalid_name_without_persist_artifacts(
    tmp_path: Path, collection_name
):
    persist_dir = tmp_path / "must-not-exist"

    with pytest.raises(ValueError, match="Chroma collection name"):
        ChromaVectorBackend(
            persist_dir=str(persist_dir),
            collection_name=collection_name,
            create_if_missing=True,
            require_ready=False,
        )

    assert not persist_dir.exists()


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


def test_chroma_creates_cosine_collection_without_initial_metadata(tmp_path: Path):
    from app.services.vector_backends.chroma_backend import ChromaVectorBackend

    backend = ChromaVectorBackend(
        persist_dir=str(tmp_path / "chroma"),
        collection_name="default_metadata_collection",
        create_if_missing=True,
        require_ready=False,
    )

    assert backend.count() == 0
    assert backend.metadata()["backend"] == "chroma"
    assert backend._collection.configuration_json["hnsw"]["space"] == "cosine"


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
        initial_metadata={
            "build_status": "building",
            "embedding_dimension": 2,
            "schema_version": 1,
        },
    )

    backend.update_build_metadata({"build_status": "ready"})

    assert backend._collection.metadata == {
        "build_status": "ready",
        "embedding_dimension": 2,
        "schema_version": 1,
    }


def _raw_chroma_collection(
    tmp_path: Path,
    name: str,
    *,
    space: str = "cosine",
    metadata: dict | None = None,
):
    client = chromadb.PersistentClient(path=str(tmp_path / "chroma"))
    collection = client.get_or_create_collection(
        name=name,
        configuration={"hnsw": {"space": space}},
        metadata=metadata,
        embedding_function=None,
    )
    return client, collection


@pytest.mark.parametrize(
    "metadata",
    [
        pytest.param({"build_status": "ready"}, id="ready-without-dimension"),
        pytest.param(
            {"build_status": "building", "embedding_dimension": True}, id="bool"
        ),
        pytest.param(
            {"build_status": "building", "embedding_dimension": 2.5}, id="float"
        ),
        pytest.param(
            {"build_status": "building", "embedding_dimension": "2"}, id="string"
        ),
        pytest.param(
            {"build_status": "building", "embedding_dimension": 0}, id="zero"
        ),
        pytest.param(
            {"build_status": "building", "embedding_dimension": -2}, id="negative"
        ),
        pytest.param({"build_status": "unknown"}, id="unknown-status"),
        pytest.param({"build_status": 1}, id="non-string-status"),
    ],
)
def test_chroma_rejects_invalid_initial_metadata_before_create(
    tmp_path: Path, metadata: dict
):
    from app.services.vector_backends.chroma_backend import ChromaVectorBackend

    persist_dir = str(tmp_path / "chroma")
    client = chromadb.PersistentClient(path=persist_dir)

    with pytest.raises(RuntimeError, match="build_status|embedding_dimension"):
        ChromaVectorBackend(
            persist_dir=persist_dir,
            collection_name="invalid_initial_metadata",
            create_if_missing=True,
            require_ready=False,
            initial_metadata=metadata,
        )

    assert client.list_collections() == []


def test_chroma_allows_building_initial_metadata_without_dimension(tmp_path: Path):
    from app.services.vector_backends.chroma_backend import ChromaVectorBackend

    backend = ChromaVectorBackend(
        persist_dir=str(tmp_path / "chroma"),
        collection_name="building_without_dimension",
        create_if_missing=True,
        require_ready=False,
        initial_metadata={"build_status": "building"},
    )

    assert backend.count() == 0


def test_chroma_rejects_ready_update_without_dimension_unchanged(tmp_path: Path):
    from app.services.vector_backends.chroma_backend import ChromaVectorBackend

    backend = ChromaVectorBackend(
        persist_dir=str(tmp_path / "chroma"),
        collection_name="invalid_ready_update",
        create_if_missing=True,
        require_ready=False,
        initial_metadata={"build_status": "building", "schema_version": 1},
    )
    before = dict(backend._collection.metadata)

    with pytest.raises(RuntimeError, match="embedding_dimension"):
        backend.update_build_metadata({"build_status": "ready"})

    fresh = backend._client.get_collection(
        "invalid_ready_update", embedding_function=None
    )
    assert fresh.metadata == before


@pytest.mark.parametrize(
    "update",
    [
        pytest.param({"embedding_dimension": 2.5}, id="invalid-dimension"),
        pytest.param({"build_status": "unknown"}, id="unknown-status"),
    ],
)
def test_chroma_rejects_invalid_metadata_update_unchanged(
    tmp_path: Path, update: dict
):
    from app.services.vector_backends.chroma_backend import ChromaVectorBackend

    backend = ChromaVectorBackend(
        persist_dir=str(tmp_path / "chroma"),
        collection_name="invalid_metadata_update",
        create_if_missing=True,
        require_ready=False,
        initial_metadata={"build_status": "building", "embedding_dimension": 2},
    )
    before = dict(backend._collection.metadata)

    with pytest.raises(RuntimeError, match="build_status|embedding_dimension"):
        backend.update_build_metadata(update)

    fresh = backend._client.get_collection(
        "invalid_metadata_update", embedding_function=None
    )
    assert fresh.metadata == before


def test_chroma_valid_build_lifecycle_reopens_ready(tmp_path: Path):
    from app.services.vector_backends.chroma_backend import ChromaVectorBackend

    kwargs = {
        "persist_dir": str(tmp_path / "chroma"),
        "collection_name": "valid_lifecycle",
    }
    backend = ChromaVectorBackend(
        **kwargs,
        create_if_missing=True,
        require_ready=False,
        initial_metadata={"build_status": "building", "schema_version": 1},
    )

    backend.update_build_metadata({"embedding_dimension": 2})
    backend.update_build_metadata({"build_status": "ready"})

    reopened = ChromaVectorBackend(**kwargs)
    assert reopened.metadata()["build_status"] == "ready"
    assert reopened.metadata()["embedding_dimension"] == 2


@pytest.mark.parametrize("create_if_missing", [False, True])
def test_chroma_rejects_existing_l2_collection(tmp_path: Path, create_if_missing: bool):
    from app.services.vector_backends.chroma_backend import ChromaVectorBackend

    _raw_chroma_collection(
        tmp_path,
        "l2_collection",
        space="l2",
        metadata={"build_status": "ready", "embedding_dimension": 2},
    )

    with pytest.raises(RuntimeError, match="cosine|space"):
        ChromaVectorBackend(
            persist_dir=str(tmp_path / "chroma"),
            collection_name="l2_collection",
            create_if_missing=create_if_missing,
            require_ready=True,
        )


def test_chroma_rejects_nonempty_ready_collection_without_dimension(tmp_path: Path):
    from app.services.vector_backends.chroma_backend import ChromaVectorBackend

    _, collection = _raw_chroma_collection(
        tmp_path,
        "missing_dimension",
        metadata={"build_status": "ready"},
    )
    collection.upsert(
        ids=["c1"],
        documents=["alpha"],
        metadatas=[{"paper_id": "p1"}],
        embeddings=[[1.0, 0.0]],
    )

    with pytest.raises(RuntimeError, match="embedding_dimension"):
        ChromaVectorBackend(
            persist_dir=str(tmp_path / "chroma"),
            collection_name="missing_dimension",
        )


@pytest.mark.parametrize(
    "dimension",
    [
        pytest.param(True, id="bool"),
        pytest.param(2.5, id="float"),
        pytest.param("2", id="string"),
        pytest.param(0, id="zero"),
        pytest.param(-2, id="negative"),
    ],
)
def test_chroma_rejects_invalid_dimension_metadata(tmp_path: Path, dimension):
    from app.services.vector_backends.chroma_backend import ChromaVectorBackend

    _raw_chroma_collection(
        tmp_path,
        "invalid_dimension",
        metadata={"build_status": "ready", "embedding_dimension": dimension},
    )

    with pytest.raises(RuntimeError, match="embedding_dimension"):
        ChromaVectorBackend(
            persist_dir=str(tmp_path / "chroma"),
            collection_name="invalid_dimension",
        )


def test_chroma_accepts_positive_builtin_int_dimension(tmp_path: Path):
    from app.services.vector_backends.chroma_backend import ChromaVectorBackend

    _raw_chroma_collection(
        tmp_path,
        "valid_dimension",
        metadata={"build_status": "ready", "embedding_dimension": 2},
    )

    backend = ChromaVectorBackend(
        persist_dir=str(tmp_path / "chroma"),
        collection_name="valid_dimension",
    )

    assert backend.metadata()["embedding_dimension"] == 2


def test_chroma_metadata_merge_refreshes_stale_client(tmp_path: Path):
    from app.services.vector_backends.chroma_backend import ChromaVectorBackend

    kwargs = {
        "persist_dir": str(tmp_path / "chroma"),
        "collection_name": "stale_metadata",
        "require_ready": False,
    }
    first = ChromaVectorBackend(
        **kwargs,
        create_if_missing=True,
        initial_metadata={
            "build_status": "building",
            "embedding_dimension": 2,
            "schema_version": 1,
        },
    )
    second = ChromaVectorBackend(**kwargs)

    second.update_build_metadata({"second_key": "second"})
    first.update_build_metadata({"first_key": "first"})

    fresh = ChromaVectorBackend(**kwargs)
    assert fresh._collection.metadata == {
        "build_status": "building",
        "embedding_dimension": 2,
        "schema_version": 1,
        "second_key": "second",
        "first_key": "first",
    }


def test_chroma_concurrent_metadata_merges_preserve_both_keys(tmp_path: Path):
    from app.services.vector_backends.chroma_backend import ChromaVectorBackend

    kwargs = {
        "persist_dir": str(tmp_path / "chroma"),
        "collection_name": "concurrent_metadata",
        "require_ready": False,
    }
    first = ChromaVectorBackend(
        **kwargs,
        create_if_missing=True,
        initial_metadata={"build_status": "building", "embedding_dimension": 2},
    )
    second = ChromaVectorBackend(**kwargs)
    barrier = threading.Barrier(3)
    errors: list[Exception] = []

    def update(backend, values):
        try:
            barrier.wait(timeout=5)
            backend.update_build_metadata(values)
        except Exception as exc:
            errors.append(exc)

    threads = [
        threading.Thread(target=update, args=(first, {"first_key": "first"})),
        threading.Thread(target=update, args=(second, {"second_key": "second"})),
    ]
    for thread in threads:
        thread.start()
    barrier.wait(timeout=5)
    for thread in threads:
        thread.join(timeout=10)

    assert not any(thread.is_alive() for thread in threads)
    assert errors == []
    fresh = ChromaVectorBackend(**kwargs)
    assert fresh._collection.metadata["first_key"] == "first"
    assert fresh._collection.metadata["second_key"] == "second"
    assert fresh._collection.metadata["build_status"] == "building"
    assert fresh._collection.metadata["embedding_dimension"] == 2


def test_chroma_metadata_paginates_only_metadatas(tmp_path: Path):
    from app.services.vector_backends.chroma_backend import ChromaVectorBackend

    _, collection = _raw_chroma_collection(
        tmp_path,
        "metadata_efficiency",
        metadata={"build_status": "ready", "embedding_dimension": 2},
    )
    size = 1001
    collection.upsert(
        ids=[f"c{index:04d}" for index in range(size)],
        documents=["content"] * size,
        metadatas=[{"paper_id": f"p{index % 3}"} for index in range(size)],
        embeddings=[[1.0, 0.0]] * size,
    )
    backend = ChromaVectorBackend(
        persist_dir=str(tmp_path / "chroma"),
        collection_name="metadata_efficiency",
    )
    instrumented_collection = backend._collection
    instrumented_collection.get = Mock(wraps=instrumented_collection.get)
    backend._client.get_collection = Mock(return_value=instrumented_collection)

    result = backend.metadata()

    assert result["chunk_count"] == size
    assert result["paper_count"] == 3
    assert instrumented_collection.get.call_count == 2
    for call in instrumented_collection.get.call_args_list:
        assert call.kwargs["include"] == ["metadatas"]


def test_chroma_query_uses_one_count_snapshot(tmp_path: Path):
    from app.services.vector_backends.chroma_backend import ChromaVectorBackend

    backend = ChromaVectorBackend(
        persist_dir=str(tmp_path / "chroma"),
        collection_name="query_count",
        create_if_missing=True,
        require_ready=False,
        initial_metadata={"build_status": "building", "embedding_dimension": 2},
    )
    instrumented_collection = backend._collection
    instrumented_collection.count = Mock(return_value=1)
    instrumented_collection.query = Mock(
        return_value={
            "ids": [["c1"]],
            "documents": [["alpha"]],
            "metadatas": [[{"paper_id": "p1"}]],
            "distances": [[0.0]],
        }
    )
    backend._client.get_collection = Mock(return_value=instrumented_collection)

    backend.query_dense([1.0, 0.0], top_k=5)

    instrumented_collection.count.assert_called_once_with()
    assert instrumented_collection.query.call_args.kwargs["n_results"] == 1


def test_chroma_empty_building_query_uses_one_count_snapshot(tmp_path: Path):
    from app.services.vector_backends.chroma_backend import ChromaVectorBackend

    backend = ChromaVectorBackend(
        persist_dir=str(tmp_path / "chroma"),
        collection_name="empty_query_count",
        create_if_missing=True,
        require_ready=False,
        initial_metadata={"build_status": "building"},
    )
    instrumented_collection = backend._collection
    instrumented_collection.count = Mock(return_value=0)
    backend._client.get_collection = Mock(return_value=instrumented_collection)

    assert backend.query_dense([1.0, 0.0], top_k=5) == []

    instrumented_collection.count.assert_called_once_with()


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
