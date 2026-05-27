import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.services.paper_manager import delete_paper_assets
from app.services.vector_store import VectorStore


class DummyVectorStore:
    def __init__(self):
        self.deleted_paper_ids = []

    def delete_paper(self, paper_id: str) -> int:
        self.deleted_paper_ids.append(paper_id)
        return 3


def _write_file(path: str, content: str = "x"):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)


def test_delete_paper_assets_removes_pdf_metadata_and_note():
    with tempfile.TemporaryDirectory() as tmpdir:
        upload_dir = os.path.join(tmpdir, "papers")
        metadata_dir = os.path.join(tmpdir, "metadata")
        note_dir = os.path.join(tmpdir, "notes")

        paper_id = "paper_20260509_001"
        pdf_path = os.path.join(upload_dir, "sample.pdf")
        metadata_path = os.path.join(metadata_dir, f"{paper_id}_parsed.json")
        note_path = os.path.join(note_dir, f"{paper_id}_note.md")

        _write_file(pdf_path, "pdf")
        _write_file(note_path, "note")
        _write_file(
            metadata_path,
            '{"paper_id":"paper_20260509_001","pdf_path":"'
            + pdf_path.replace("\\", "\\\\")
            + '","title":"T","abstract":"A","sections":[],"full_text":"F"}',
        )

        vector_store = DummyVectorStore()
        result = delete_paper_assets(
            paper_id, upload_dir, metadata_dir, note_dir, vector_store
        )

        assert result["status"] == "deleted"
        assert result["paper_id"] == paper_id
        assert result["deleted_chunks"] == 3
        assert vector_store.deleted_paper_ids == [paper_id]
        assert not os.path.exists(pdf_path)
        assert not os.path.exists(metadata_path)
        assert not os.path.exists(note_path)


def test_delete_paper_assets_ignores_missing_note_and_pdf():
    with tempfile.TemporaryDirectory() as tmpdir:
        upload_dir = os.path.join(tmpdir, "papers")
        metadata_dir = os.path.join(tmpdir, "metadata")
        note_dir = os.path.join(tmpdir, "notes")

        paper_id = "paper_20260509_002"
        metadata_path = os.path.join(metadata_dir, f"{paper_id}_parsed.json")
        _write_file(
            metadata_path,
            '{"paper_id":"paper_20260509_002","pdf_path":"","title":"T","abstract":"A","sections":[],"full_text":"F"}',
        )

        vector_store = DummyVectorStore()
        result = delete_paper_assets(
            paper_id, upload_dir, metadata_dir, note_dir, vector_store
        )

        assert result["deleted_chunks"] == 3
        assert not os.path.exists(metadata_path)
