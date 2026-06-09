from __future__ import annotations

import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Protocol

from pydantic import BaseModel

from app.research_workflow.schemas import (
    ResearchRunPaperArtifact,
    ResearchRunPaperItem,
)
from app.schemas import Chunk, PaperParseResult
from app.services.chunker import chunk_paper
from app.services.markdown_exporter import save_markdown
from app.services.pdf_parser import generate_paper_id, parse_pdf, save_parse_result


class EmbeddingProvider(Protocol):
    device: str
    batch_size: int

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        ...


class VectorStoreProvider(Protocol):
    def add_chunks(self, chunks: list[Chunk], embeddings: list[list[float]]) -> int:
        ...

    def backend_name(self) -> str:
        ...

    def metadata(self) -> dict:
        ...


class PaperProcessingResult(BaseModel):
    item: ResearchRunPaperItem
    chunk_count: int = 0
    note_path: str | None = None
    vector_backend: str | None = None


class PaperProcessingService:
    def __init__(
        self,
        upload_dir: str | Path,
        metadata_dir: str | Path,
        note_dir: str | Path,
        vector_store: VectorStoreProvider,
        embedding_client: EmbeddingProvider,
        parse_pdf_func: Callable[[str, str], PaperParseResult] = parse_pdf,
        note_generator_func: Callable[[str, str], str] | None = None,
        paper_id_generator: Callable[[str], str] = generate_paper_id,
    ) -> None:
        self.upload_dir = Path(upload_dir)
        self.metadata_dir = Path(metadata_dir)
        self.note_dir = Path(note_dir)
        self.vector_store = vector_store
        self.embedding_client = embedding_client
        self.parse_pdf_func = parse_pdf_func
        self.note_generator_func = note_generator_func or self._generate_note
        self.paper_id_generator = paper_id_generator

    def process_item(
        self, item: ResearchRunPaperItem, run_output_dir: str | Path
    ) -> PaperProcessingResult:
        started_at = datetime.now(timezone.utc)
        running = item.model_copy(
            update={
                "status": "running",
                "progress": 0.05,
                "started_at": started_at,
                "updated_at": started_at,
            }
        )
        try:
            if not running.pdf_path:
                raise FileNotFoundError("No local PDF attachment found")

            paper_id = self.paper_id_generator(str(self.upload_dir))
            stored_pdf = self._copy_pdf(Path(running.pdf_path), paper_id)
            parsed = self.parse_pdf_func(str(stored_pdf), paper_id)
            metadata_path = save_parse_result(parsed, str(self.metadata_dir))
            chunks = chunk_paper(parsed)
            if not chunks:
                raise ValueError("Paper content produced no indexable chunks")

            embeddings = self.embedding_client.embed_texts(
                [chunk.content for chunk in chunks]
            )
            self.vector_store.add_chunks(chunks, embeddings)
            markdown = self.note_generator_func(paper_id, str(self.metadata_dir))
            note_path = save_markdown(paper_id, markdown, str(self.note_dir))
            run_note_path = self._write_run_paper_note(
                run_output_dir, paper_id, markdown
            )

            completed_at = datetime.now(timezone.utc)
            completed = running.model_copy(
                update={
                    "paper_id": paper_id,
                    "pdf_path": str(stored_pdf),
                    "status": "completed",
                    "progress": 1.0,
                    "error": None,
                    "artifacts": [
                        ResearchRunPaperArtifact(
                            label="PDF", path=str(stored_pdf), kind="pdf"
                        ),
                        ResearchRunPaperArtifact(
                            label="Parsed Metadata",
                            path=str(metadata_path),
                            kind="json",
                        ),
                        ResearchRunPaperArtifact(
                            label="Paper Note",
                            path=str(run_note_path),
                            kind="markdown",
                        ),
                        ResearchRunPaperArtifact(
                            label="Vector Index",
                            path=self.vector_store.metadata().get("store_path", ""),
                            kind="vector_index",
                        ),
                    ],
                    "updated_at": completed_at,
                    "completed_at": completed_at,
                }
            )
            return PaperProcessingResult(
                item=completed,
                chunk_count=len(chunks),
                note_path=str(note_path),
                vector_backend=self.vector_store.backend_name(),
            )
        except Exception as exc:
            failed_at = datetime.now(timezone.utc)
            failed = running.model_copy(
                update={
                    "status": "failed",
                    "progress": 1.0,
                    "error": str(exc),
                    "updated_at": failed_at,
                    "completed_at": failed_at,
                }
            )
            return PaperProcessingResult(
                item=failed,
                chunk_count=0,
                vector_backend=self._safe_vector_backend(),
            )

    def _copy_pdf(self, source: Path, paper_id: str) -> Path:
        if not source.is_file():
            raise FileNotFoundError(f"PDF file not found: {source}")
        self.upload_dir.mkdir(parents=True, exist_ok=True)
        target = self.upload_dir / f"{paper_id}.pdf"
        shutil.copy2(source, target)
        return target

    def _write_run_paper_note(
        self, run_output_dir: str | Path, paper_id: str, markdown: str
    ) -> Path:
        papers_dir = Path(run_output_dir) / "papers"
        papers_dir.mkdir(parents=True, exist_ok=True)
        path = papers_dir / f"{paper_id}.md"
        path.write_text(markdown, encoding="utf-8")
        return path

    def _generate_note(self, paper_id: str, metadata_dir: str) -> str:
        from app.services.note_generator import generate_note

        return generate_note(paper_id, metadata_dir=metadata_dir)

    def _safe_vector_backend(self) -> str | None:
        try:
            return self.vector_store.backend_name()
        except Exception:
            return None
