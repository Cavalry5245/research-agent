from datetime import datetime, timezone
from pathlib import Path

from app.research_workflow.paper_processing import PaperProcessingService
from app.research_workflow.schemas import ResearchRunPaperItem
from app.schemas import PaperParseResult, Section


class FakeEmbeddingClient:
    device = "cpu"
    batch_size = 2

    def embed_texts(self, texts):
        return [[1.0, 0.0, 0.0] for _ in texts]


class FakeVectorStore:
    def __init__(self):
        self.added = []

    def add_chunks(self, chunks, embeddings):
        self.added.append((chunks, embeddings))
        return len(chunks)

    def backend_name(self):
        return "fake"

    def metadata(self):
        return {"store_path": "fake/vector_store.json", "chunk_count": 2}


def _item(pdf_path: Path) -> ResearchRunPaperItem:
    now = datetime.now(timezone.utc)
    return ResearchRunPaperItem(
        item_id="zotero_A1",
        title="Paper A",
        zotero_item_id="A1",
        pdf_path=str(pdf_path),
        created_at=now,
        updated_at=now,
    )


def test_paper_processing_copies_parses_indexes_and_generates_note(tmp_path):
    source_pdf = tmp_path / "source.pdf"
    source_pdf.write_bytes(b"%PDF fake")
    upload_dir = tmp_path / "papers"
    metadata_dir = tmp_path / "metadata"
    note_dir = tmp_path / "notes"
    vault_run_dir = tmp_path / "vault" / "ResearchAgent" / "Runs" / "demo"
    vault_run_dir.mkdir(parents=True)

    def fake_parse(pdf_path, paper_id):
        return PaperParseResult(
            paper_id=paper_id,
            title="Parsed Paper A",
            abstract="Abstract A",
            sections=[
                Section(
                    heading="Method",
                    content="This method section is long enough to chunk.",
                )
            ],
            full_text="This method section is long enough to chunk.",
            pdf_path=pdf_path,
        )

    service = PaperProcessingService(
        upload_dir=upload_dir,
        metadata_dir=metadata_dir,
        note_dir=note_dir,
        vector_store=FakeVectorStore(),
        embedding_client=FakeEmbeddingClient(),
        parse_pdf_func=fake_parse,
        note_generator_func=lambda paper_id, metadata_dir: "# Note for Paper A",
        paper_id_generator=lambda upload_dir: "paper_20260609_001",
    )

    result = service.process_item(_item(source_pdf), vault_run_dir)

    assert result.item.status == "completed"
    assert result.item.paper_id == "paper_20260609_001"
    assert Path(result.item.pdf_path).is_file()
    assert (metadata_dir / "paper_20260609_001_parsed.json").is_file()
    assert (note_dir / "paper_20260609_001_note.md").is_file()
    assert (
        vault_run_dir / "papers" / "paper_20260609_001.md"
    ).read_text(encoding="utf-8") == "# Note for Paper A"
    assert result.chunk_count == 1
    assert result.note_path.endswith("paper_20260609_001_note.md")


def test_paper_processing_failed_parse_returns_failed_item(tmp_path):
    source_pdf = tmp_path / "source.pdf"
    source_pdf.write_bytes(b"%PDF fake")

    def failing_parse(pdf_path, paper_id):
        raise ValueError("bad pdf")

    service = PaperProcessingService(
        upload_dir=tmp_path / "papers",
        metadata_dir=tmp_path / "metadata",
        note_dir=tmp_path / "notes",
        vector_store=FakeVectorStore(),
        embedding_client=FakeEmbeddingClient(),
        parse_pdf_func=failing_parse,
        note_generator_func=lambda paper_id, metadata_dir: "# not reached",
        paper_id_generator=lambda upload_dir: "paper_20260609_001",
    )

    result = service.process_item(_item(source_pdf), tmp_path / "vault")

    assert result.item.status == "failed"
    assert result.item.error == "bad pdf"
    assert result.item.progress == 1.0
    assert result.item.completed_at is not None
    assert result.chunk_count == 0


def test_paper_processing_missing_pdf_returns_failed_item(tmp_path):
    missing_pdf = tmp_path / "missing.pdf"
    service = PaperProcessingService(
        upload_dir=tmp_path / "papers",
        metadata_dir=tmp_path / "metadata",
        note_dir=tmp_path / "notes",
        vector_store=FakeVectorStore(),
        embedding_client=FakeEmbeddingClient(),
        paper_id_generator=lambda upload_dir: "paper_20260609_001",
    )

    result = service.process_item(_item(missing_pdf), tmp_path / "vault")

    assert result.item.status == "failed"
    assert f"PDF file not found: {missing_pdf}" == result.item.error
    assert result.chunk_count == 0
