import os
import sys
from unittest.mock import MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.schemas import Chunk
from app.services.incremental_indexer import IncrementalIndexer


def _mk_chunk(chunk_id: str, content: str, paper_id: str = "p1") -> Chunk:
    return Chunk(
        chunk_id=chunk_id, paper_id=paper_id, title="t", section="s", content=content
    )


def _mk_store_chunks(chunks):
    return [
        {"chunk_id": c.chunk_id, "content": c.content, "paper_id": c.paper_id}
        for c in chunks
    ]


def test_incremental_index_adds_new_chunks_only():
    vs = MagicMock()
    vs.list_chunks.return_value = _mk_store_chunks([_mk_chunk("c1", "old text")])
    vs.add_chunks.return_value = 1
    emb = MagicMock()
    emb.embed_texts.return_value = [[0.1]]

    idx = IncrementalIndexer(vs, emb)
    new = [_mk_chunk("c1", "old text"), _mk_chunk("c2", "new text")]
    result = idx.update_paper_index("p1", new)

    assert result["added"] == 1
    assert result["unchanged"] == 1
    assert result["removed"] == 0
    emb.embed_texts.assert_called_once_with(["new text"])


def test_incremental_index_removes_missing_chunks():
    vs = MagicMock()
    vs.list_chunks.return_value = _mk_store_chunks(
        [_mk_chunk("c1", "x"), _mk_chunk("c2", "y")]
    )
    vs.delete_chunks.return_value = 1
    vs.add_chunks.return_value = 0
    emb = MagicMock()

    idx = IncrementalIndexer(vs, emb)
    new = [_mk_chunk("c1", "x")]
    result = idx.update_paper_index("p1", new)

    assert result["removed"] == 1
    assert result["added"] == 0
    vs.delete_chunks.assert_called_once_with(["c2"])
    emb.embed_texts.assert_not_called()


def test_incremental_index_reembeds_modified_chunk():
    vs = MagicMock()
    vs.list_chunks.return_value = _mk_store_chunks([_mk_chunk("c1", "old")])
    vs.add_chunks.return_value = 1
    emb = MagicMock()
    emb.embed_texts.return_value = [[0.2]]

    idx = IncrementalIndexer(vs, emb)
    new = [_mk_chunk("c1", "modified")]
    result = idx.update_paper_index("p1", new)

    assert result["added"] == 1
    assert result["unchanged"] == 0


def test_incremental_index_no_existing_chunks_adds_all():
    vs = MagicMock()
    vs.list_chunks.return_value = []
    vs.add_chunks.return_value = 2
    emb = MagicMock()
    emb.embed_texts.return_value = [[0.1], [0.2]]

    idx = IncrementalIndexer(vs, emb)
    new = [_mk_chunk("a", "x"), _mk_chunk("b", "y")]
    result = idx.update_paper_index("p1", new)

    assert result["added"] == 2
    assert result["removed"] == 0
