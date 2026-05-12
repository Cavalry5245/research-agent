import os
import sys
import tempfile
from unittest.mock import patch

from fastapi.testclient import TestClient

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.main import app
from app.schemas import PaperParseResult, Section
from app.services.vector_store import VectorStore


def _make_parsed_result(paper_id: str = "paper_A") -> dict:
    return PaperParseResult(
        paper_id=paper_id,
        title="Paper A",
        abstract="Abstract",
        sections=[
            Section(heading="Method", content="A" * 1200),
            Section(heading="Experiment", content="B" * 900),
        ],
        full_text=("A" * 1200) + ("B" * 900),
    ).model_dump()


class FakeEmbeddingClient:
    def embed_texts(self, texts):
        return [[0.1, 0.2, 0.3] for _ in texts]


def test_index_endpoint_returns_timing_and_avoids_repeat_indexing():
    client = TestClient(app)

    with tempfile.TemporaryDirectory() as tmpdir:
        store = VectorStore(persist_dir=os.path.join(tmpdir, "vectors"))
        parsed = _make_parsed_result("paper_A")

        with patch("app.main._vector_store", store), patch(
            "app.main.load_parsed_result", return_value=parsed
        ), patch("app.main.EmbeddingClient", return_value=FakeEmbeddingClient()):
            first = client.post("/papers/paper_A/index")
            assert first.status_code == 200
            body1 = first.json()
            assert body1["status"] == "indexed"
            assert body1["already_indexed"] is False
            assert body1["chunks_indexed"] > 0
            assert body1["embedding_seconds"] >= 0.0
            assert body1["persist_seconds"] >= 0.0
            assert body1["total_seconds"] >= 0.0

            second = client.post("/papers/paper_A/index")
            assert second.status_code == 200
            body2 = second.json()
            assert body2["status"] == "already_indexed"
            assert body2["already_indexed"] is True
            assert body2["chunks_indexed"] == body1["chunks_indexed"]

            forced = client.post("/papers/paper_A/index?force=true")
            assert forced.status_code == 200
            body3 = forced.json()
            assert body3["status"] == "indexed"
            assert body3["already_indexed"] is False
