"""Multi-embedding-model real evaluation script.

For each requested model: load the SentenceTransformer model, re-embed all
chunks from the production vector store (or reuse cached embeddings if the
model matches the one used to build the store), embed the 168 QA queries,
and compute per-sample paper-scoped retrieval metrics (hit@5, MRR,
retrieval_time). Section matching is case-insensitive.

Limitations surfaced honestly: samples whose `supporting_sections` reference
a section absent from the indexed corpus (e.g. "Abstract" chunks are not
indexed in the current vector store) will record 0 hit/MRR for all models,
so paper-level recall is also reported as a relaxed signal.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any

import numpy as np

DEFAULT_DATASET = Path("app/evaluation/datasets/qa_eval_seed.jsonl")
DEFAULT_VECTOR_STORE = Path("app/storage/vector_db/vector_store.json")
DEFAULT_OUTPUT = Path("app/experiments/reports")


def _load_dataset(path: Path) -> list[dict]:
    if not path.exists():
        return []
    samples: list[dict] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            samples.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return samples


def _load_chunks(vector_store_path: Path) -> tuple[list[dict], np.ndarray | None]:
    """Return (chunks, cached_embeddings or None). Each chunk dict has keys:
    paper_id, section, content, chunk_id, etc. Cached embeddings are aligned
    by index when present.

    Filters out entries whose cached embedding dimension does not match the
    majority dimension (defensive against test-data pollution).
    """
    data = json.loads(vector_store_path.read_text(encoding="utf-8"))
    from collections import Counter

    dim_counter = Counter(
        len(entry.get("embedding") or [])
        for entry in data
        if isinstance(entry.get("embedding"), list)
    )
    if not dim_counter:
        majority_dim = None
    else:
        majority_dim, _ = dim_counter.most_common(1)[0]

    chunks: list[dict] = []
    embs: list[list[float]] = []
    dropped = 0
    for entry in data:
        c = entry.get("chunk") or {}
        e = entry.get("embedding")
        if not c:
            continue
        if majority_dim is not None and isinstance(e, list) and len(e) != majority_dim:
            dropped += 1
            continue
        if not isinstance(e, list) or not e:
            dropped += 1
            continue
        chunks.append(c)
        embs.append(e)
    if dropped:
        print(
            f"[_load_chunks] dropped {dropped} entries with non-majority embedding dim",
            file=sys.stderr,
        )
    cached = np.asarray(embs, dtype=np.float32) if embs else None
    return chunks, cached


def _normalize_sections(secs: list[str] | None) -> set[str]:
    return {s.strip().lower() for s in (secs or []) if s}


def _cosine_similarity_matrix(queries: np.ndarray, docs: np.ndarray) -> np.ndarray:
    qn = queries / (np.linalg.norm(queries, axis=1, keepdims=True) + 1e-12)
    dn = docs / (np.linalg.norm(docs, axis=1, keepdims=True) + 1e-12)
    return qn @ dn.T


def _score_sample(
    sample: dict,
    chunks: list[dict],
    sim_row: np.ndarray,
    top_k: int,
) -> dict[str, float]:
    paper_id = sample.get("paper_id")
    expected = _normalize_sections(sample.get("supporting_sections"))

    paper_idx = [i for i, c in enumerate(chunks) if c.get("paper_id") == paper_id]
    if not paper_idx:
        return {"hit_at_k": 0.0, "rr": 0.0, "paper_hit": 0.0, "scoped_chunks": 0.0}

    paper_scores = [(i, float(sim_row[i])) for i in paper_idx]
    paper_scores.sort(key=lambda t: t[1], reverse=True)
    top = paper_scores[:top_k]

    hit_at_k = 0.0
    rr = 0.0
    for rank, (idx, _) in enumerate(top, start=1):
        sec = (chunks[idx].get("section") or "").strip().lower()
        if sec and sec in expected:
            hit_at_k = 1.0
            rr = 1.0 / rank
            break

    return {
        "hit_at_k": hit_at_k,
        "rr": rr,
        "paper_hit": 1.0,
        "scoped_chunks": float(len(paper_idx)),
    }


def evaluate_model(
    model_name: str,
    samples: list[dict],
    chunks: list[dict],
    cached_emb: np.ndarray | None,
    cache_compatible: bool,
    top_k: int = 5,
) -> dict[str, Any]:
    from app.services.embedding_client import EmbeddingClient

    client = EmbeddingClient(model_name=model_name)

    embed_start = time.perf_counter()
    if cache_compatible and cached_emb is not None:
        chunk_emb = cached_emb
        chunk_embed_seconds = 0.0
    else:
        contents = [c.get("content", "") for c in chunks]
        chunk_emb_list = client.embed_texts(contents)
        chunk_emb = np.asarray(chunk_emb_list, dtype=np.float32)
        chunk_embed_seconds = time.perf_counter() - embed_start

    query_start = time.perf_counter()
    queries = [s.get("question", "") for s in samples]
    query_emb_list = client.embed_texts(queries)
    query_emb = np.asarray(query_emb_list, dtype=np.float32)
    query_embed_seconds = time.perf_counter() - query_start

    sim_start = time.perf_counter()
    sim = _cosine_similarity_matrix(query_emb, chunk_emb)
    sim_seconds = time.perf_counter() - sim_start

    hits = []
    rrs = []
    paper_hits = []
    scoped_counts = []
    for i, sample in enumerate(samples):
        m = _score_sample(sample, chunks, sim[i], top_k)
        hits.append(m["hit_at_k"])
        rrs.append(m["rr"])
        paper_hits.append(m["paper_hit"])
        scoped_counts.append(m["scoped_chunks"])

    per_query_retrieval_seconds = (query_embed_seconds + sim_seconds) / max(
        1, len(samples)
    )

    return {
        "model": model_name,
        "metrics": {
            "hit_at_5": float(np.mean(hits)) if hits else 0.0,
            "mrr": float(np.mean(rrs)) if rrs else 0.0,
            "retrieval_time": round(per_query_retrieval_seconds, 4),
            "paper_recall": float(np.mean(paper_hits)) if paper_hits else 0.0,
            "sample_count": float(len(samples)),
            "chunk_count": float(len(chunks)),
            "chunk_embed_seconds": round(chunk_embed_seconds, 2),
            "query_embed_seconds": round(query_embed_seconds, 2),
            "similarity_seconds": round(sim_seconds, 4),
            "cache_reused": cache_compatible and cached_emb is not None,
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Real evaluation of one or more embedding models."
    )
    parser.add_argument(
        "--models",
        nargs="+",
        default=["bge-small-zh-v1.5", "bge-large-zh-v1.5", "m3e-base"],
    )
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET)
    parser.add_argument("--vector-store", type=Path, default=DEFAULT_VECTOR_STORE)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument(
        "--cache-model",
        type=str,
        default="bge-small-zh-v1.5",
        help="Model name whose cached embeddings in --vector-store should be reused.",
    )
    args = parser.parse_args()

    samples = _load_dataset(args.dataset)
    if not samples:
        print(f"No samples loaded from {args.dataset}", file=sys.stderr)
        sys.exit(2)

    chunks, cached_emb = _load_chunks(args.vector_store)
    if not chunks:
        print(f"No chunks loaded from {args.vector_store}", file=sys.stderr)
        sys.exit(2)

    print(
        f"Loaded {len(samples)} samples and {len(chunks)} chunks "
        f"({'cached embeddings available' if cached_emb is not None else 'no cache'})",
        file=sys.stderr,
    )

    records = []
    for m in args.models:
        cache_compatible = m == args.cache_model
        print(
            f"\n[evaluate_embeddings] Model={m} cache_compatible={cache_compatible}",
            file=sys.stderr,
        )
        t0 = time.perf_counter()
        record = evaluate_model(
            m, samples, chunks, cached_emb, cache_compatible, top_k=args.top_k
        )
        print(
            f"  ↳ hit@{args.top_k}={record['metrics']['hit_at_5']:.4f}, "
            f"mrr={record['metrics']['mrr']:.4f}, "
            f"retrieval_time={record['metrics']['retrieval_time']:.4f}s, "
            f"elapsed={time.perf_counter()-t0:.1f}s",
            file=sys.stderr,
        )
        records.append(record)

    args.output_dir.mkdir(parents=True, exist_ok=True)
    json_path = args.output_dir / "embedding_models_real_report.json"
    md_path = args.output_dir / "embedding_models_real_report.md"

    json_path.write_text(
        json.dumps(
            {
                "mode": "live full",
                "models": records,
                "dataset": str(args.dataset),
                "vector_store": str(args.vector_store),
                "sample_count": len(samples),
                "chunk_count": len(chunks),
                "top_k": args.top_k,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    md_lines = [
        "# Embedding Models Real Evaluation",
        "",
        f"Dataset: `{args.dataset}` ({len(samples)} samples)",
        f"Corpus: `{args.vector_store}` ({len(chunks)} chunks)",
        f"Mode: **live full** (real embeddings, paper-scoped retrieval, top_k={args.top_k})",
        "",
        "## Per-Model Metrics",
        "",
        "| Model | hit@5 | MRR | paper_recall | retrieval_time (s/q) | cache_reused |",
        "|---|---|---|---|---|---|",
    ]
    for r in records:
        m = r["metrics"]
        md_lines.append(
            f"| {r['model']} | {m['hit_at_5']:.4f} | {m['mrr']:.4f} | "
            f"{m['paper_recall']:.4f} | {m['retrieval_time']:.4f} | {m['cache_reused']!s} |"
        )
    md_lines += [
        "",
        "## Recommendation",
        "",
    ]
    best = max(records, key=lambda r: r["metrics"]["hit_at_5"])
    md_lines.append(
        f"**Highest hit@5**: `{best['model']}` (hit@5={best['metrics']['hit_at_5']:.4f}, "
        f"MRR={best['metrics']['mrr']:.4f})"
    )
    md_lines += [
        "",
        "## Notes",
        "",
        "- Section match is case-insensitive against `supporting_sections`.",
        "- Retrieval is paper-scoped (filtered to `chunk.paper_id == sample.paper_id`), matching production behavior.",
        "- `paper_recall` is a relaxed signal: 1.0 means the sample's paper is present in the corpus; metric is intended to surface data-coverage gaps when hit@5 looks low.",
        "- If hit@5 is materially below `paper_recall`, the gap reflects section-level retrieval quality, not corpus coverage.",
    ]

    md_path.write_text("\n".join(md_lines), encoding="utf-8")

    print(f"\nWrote {md_path} and {json_path}")


if __name__ == "__main__":
    main()
