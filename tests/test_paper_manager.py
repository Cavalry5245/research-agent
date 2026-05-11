import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.schemas import Chunk, PaperParseResult, Section
from app.services.paper_manager import delete_paper_assets
from app.services.vector_store import VectorStore


def _make_chunk(paper_id: str, section: str, content: str, seq: int) -> Chunk:
    return Chunk(
        chunk_id=f"{paper_id}_chunk_{seq:04d}",
        paper_id=paper_id,
        title=f"Paper {paper_id}",
        section=section,
        content=content,
    )


def test_delete_paper_assets_removes_pdf_metadata_note_and_index():
    with tempfile.TemporaryDirectory() as tmpdir:
        upload_dir = os.path.join(tmpdir, "papers")
        metadata_dir = os.path.join(tmpdir, "metadata")
        note_dir = os.path.join(tmpdir, "notes")
        vector_dir = os.path.join(tmpdir, "vector_db")
        os.makedirs(upload_dir, exist_ok=True)
        os.makedirs(metadata_dir, exist_ok=True)
        os.makedirs(note_dir, exist_ok=True)

        paper_id = "paper_20260509_001"
        pdf_path = os.path.join(upload_dir, "sample.pdf")
        metadata_path = os.path.join(metadata_dir, f"{paper_id}_parsed.json")
        note_path = os.path.join(note_dir, f"{paper_id}_note.md")

        with open(pdf_path, "wb") as f:
            f.write(b"%PDF-1.4 test")

        parsed = PaperParseResult(
            paper_id=paper_id,
            title="Test Paper",
            abstract="Abstract",
            sections=[Section(heading="Introduction", content="Intro")],
            full_text="Full text",
            pdf_path=pdf_path,
        )
        with open(metadata_path, "w", encoding="utf-8") as f:
            f.write(parsed.model_dump_json(indent=2))

        with open(note_path, "w", encoding="utf-8") as f:
            f.write("# Note")

        store = VectorStore(persist_dir=vector_dir)
        chunk = _make_chunk(paper_id, "Introduction", "infrared detection", 1)
        store.add_chunks([chunk], [[0.1, 0.2, 0.3]])
        assert store.count() == 1

        result = delete_paper_assets(
            paper_id=paper_id,
            upload_dir=upload_dir,
            metadata_dir=metadata_dir,
            note_dir=note_dir,
            vector_store=store,
        )

        assert result["paper_id"] == paper_id
        assert result["status"] == "deleted"
        assert result["deleted_chunks"] == 1
        assert set(result["deleted_files"]) == {pdf_path, metadata_path, note_path}
        assert not os.path.exists(pdf_path)
        assert not os.path.exists(metadata_path)
        assert not os.path.exists(note_path)

        reloaded = VectorStore(persist_dir=vector_dir)
        assert reloaded.count() == 0


def test_delete_paper_assets_requires_metadata():
    with tempfile.TemporaryDirectory() as tmpdir:
        upload_dir = os.path.join(tmpdir, "papers")
        metadata_dir = os.path.join(tmpdir, "metadata")
        note_dir = os.path.join(tmpdir, "notes")
        os.makedirs(upload_dir, exist_ok=True)
        os.makedirs(metadata_dir, exist_ok=True)
        os.makedirs(note_dir, exist_ok=True)

        try:
            delete_paper_assets(
                paper_id="paper_missing",
                upload_dir=upload_dir,
                metadata_dir=metadata_dir,
                note_dir=note_dir,
                vector_store=VectorStore(persist_dir=os.path.join(tmpdir, "vector_db")),
            )
            assert False, "Should have raised FileNotFoundError"
        except FileNotFoundError:
            pass
