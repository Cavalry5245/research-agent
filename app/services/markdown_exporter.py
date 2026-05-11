import os


def save_markdown(paper_id: str, content: str, note_dir: str) -> str:
    os.makedirs(note_dir, exist_ok=True)
    filepath = os.path.join(note_dir, f"{paper_id}_note.md")
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(content)
    return filepath
