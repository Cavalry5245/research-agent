import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.services.index_version import IndexVersionStore


def test_record_version_increments_per_paper():
    with tempfile.TemporaryDirectory() as tmp:
        store = IndexVersionStore(Path(tmp) / "versions.json")

        v1 = store.record_version("p1", chunk_count=10, embedding_model="bge-small")
        v2 = store.record_version("p1", chunk_count=12, embedding_model="bge-small")
        v_other = store.record_version("p2", chunk_count=5, embedding_model="bge-large")

        assert v1["version"] == 1
        assert v2["version"] == 2
        assert v_other["version"] == 1


def test_list_versions_and_latest():
    with tempfile.TemporaryDirectory() as tmp:
        store = IndexVersionStore(Path(tmp) / "versions.json")
        store.record_version("p1", chunk_count=10, embedding_model="m1")
        store.record_version("p1", chunk_count=20, embedding_model="m2")

        versions = store.list_versions("p1")
        assert len(versions) == 2
        assert store.latest("p1")["version"] == 2
        assert store.latest("p1")["embedding_model"] == "m2"


def test_rollback_truncates_to_version():
    with tempfile.TemporaryDirectory() as tmp:
        store = IndexVersionStore(Path(tmp) / "versions.json")
        store.record_version("p1", chunk_count=10, embedding_model="m1")
        store.record_version("p1", chunk_count=20, embedding_model="m2")
        store.record_version("p1", chunk_count=30, embedding_model="m3")

        target = store.rollback_to("p1", version=2)

        assert target["chunk_count"] == 20
        assert len(store.list_versions("p1")) == 2
        assert store.latest("p1")["version"] == 2


def test_rollback_to_missing_version_returns_none():
    with tempfile.TemporaryDirectory() as tmp:
        store = IndexVersionStore(Path(tmp) / "versions.json")
        store.record_version("p1", chunk_count=10, embedding_model="m1")
        assert store.rollback_to("p1", version=99) is None


def test_extra_fields_persist():
    with tempfile.TemporaryDirectory() as tmp:
        store = IndexVersionStore(Path(tmp) / "versions.json")
        v = store.record_version(
            "p1", chunk_count=10, embedding_model="m1", extra={"chunk_size": 800}
        )
        assert v["chunk_size"] == 800
        assert store.list_versions("p1")[0]["chunk_size"] == 800
