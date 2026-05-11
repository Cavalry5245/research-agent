import os

from app.services.pdf_parser import load_parsed_result


def delete_paper_assets(
    paper_id: str,
    upload_dir: str,
    metadata_dir: str,
    note_dir: str,
    vector_store,
) -> dict:
    data = load_parsed_result(paper_id, metadata_dir)

    deleted_files: list[str] = []

    pdf_path = data.get("pdf_path", "")
    if pdf_path and os.path.isfile(pdf_path):
        os.remove(pdf_path)
        deleted_files.append(pdf_path)

    metadata_path = os.path.join(metadata_dir, f"{paper_id}_parsed.json")
    if os.path.isfile(metadata_path):
        os.remove(metadata_path)
        deleted_files.append(metadata_path)

    note_path = os.path.join(note_dir, f"{paper_id}_note.md")
    if os.path.isfile(note_path):
        os.remove(note_path)
        deleted_files.append(note_path)

    deleted_chunks = vector_store.delete_paper(paper_id)

    return {
        "paper_id": paper_id,
        "status": "deleted",
        "deleted_files": deleted_files,
        "deleted_chunks": deleted_chunks,
    }
