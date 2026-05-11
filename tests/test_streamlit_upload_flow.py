import os
import sys
from io import BytesIO

import fitz

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.services.pdf_parser import generate_paper_id, parse_pdf, save_parse_result


def _create_pdf_bytes(title: str, body: str) -> bytes:
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), title, fontsize=20)
    page.insert_text((72, 110), body, fontsize=12)
    data = doc.tobytes()
    doc.close()
    return data


def _save_uploaded_files(uploaded_files, upload_dir: str) -> list[dict]:
    os.makedirs(upload_dir, exist_ok=True)
    saved_files = []

    for uploaded in uploaded_files:
        paper_id = generate_paper_id(upload_dir)
        storage_path = os.path.join(upload_dir, uploaded.name)
        if os.path.exists(storage_path):
            name, ext = os.path.splitext(uploaded.name)
            storage_path = os.path.join(upload_dir, f"{name}__new{ext}")

        with open(storage_path, "wb") as f:
            f.write(uploaded.getbuffer())

        saved_files.append(
            {
                "paper_id": paper_id,
                "filename": uploaded.name,
                "storage_path": storage_path,
            }
        )

    return saved_files


def _parse_saved_files(saved_files: list[dict], metadata_dir: str) -> list[dict]:
    parsed_results = []

    for item in saved_files:
        result = parse_pdf(item["storage_path"], item["paper_id"])
        save_parse_result(result, metadata_dir)
        parsed_results.append(
            {
                "paper_id": item["paper_id"],
                "filename": item["filename"],
                "title": result.title,
                "sections": len(result.sections),
                "chars": len(result.full_text),
            }
        )

    return parsed_results


class FakeUpload:
    def __init__(self, name: str, data: bytes):
        self.name = name
        self._data = data

    def getbuffer(self):
        return memoryview(self._data)


def test_save_uploaded_files_supports_multiple_pdfs():
    import tempfile

    with tempfile.TemporaryDirectory() as tmpdir:
        uploads = [
            FakeUpload("paper_a.pdf", _create_pdf_bytes("Paper A", "Body A")),
            FakeUpload("paper_b.pdf", _create_pdf_bytes("Paper B", "Body B")),
        ]

        saved = _save_uploaded_files(uploads, tmpdir)

        assert len(saved) == 2
        assert saved[0]["filename"] == "paper_a.pdf"
        assert saved[1]["filename"] == "paper_b.pdf"
        assert os.path.exists(saved[0]["storage_path"])
        assert os.path.exists(saved[1]["storage_path"])
        assert saved[0]["paper_id"] != saved[1]["paper_id"]


def test_save_uploaded_files_renames_duplicate_filename():
    import tempfile

    with tempfile.TemporaryDirectory() as tmpdir:
        first = FakeUpload("paper.pdf", _create_pdf_bytes("Paper A", "Body A"))
        second = FakeUpload("paper.pdf", _create_pdf_bytes("Paper B", "Body B"))

        saved = _save_uploaded_files([first, second], tmpdir)

        assert saved[0]["storage_path"].endswith("paper.pdf")
        assert saved[1]["storage_path"].endswith("paper__new.pdf")


def test_parse_saved_files_runs_only_when_called():
    import tempfile

    with tempfile.TemporaryDirectory() as tmpdir:
        uploads = [FakeUpload("paper.pdf", _create_pdf_bytes("Paper A", "Body A"))]
        saved = _save_uploaded_files(uploads, os.path.join(tmpdir, "papers"))
        metadata_dir = os.path.join(tmpdir, "metadata")

        parsed = _parse_saved_files(saved, metadata_dir)

        assert len(parsed) == 1
        assert parsed[0]["filename"] == "paper.pdf"
        assert parsed[0]["paper_id"].startswith("paper_")
        metadata_files = os.listdir(metadata_dir)
        assert len(metadata_files) == 1
        assert metadata_files[0].endswith("_parsed.json")
