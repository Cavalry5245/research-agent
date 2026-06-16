"""Real per-scenario executors for ExperimentRunner.

Each `make_real_executor(scenario_name)` returns a `variant_fn(VariantConfig)
-> dict[str, float]` that runs the actual pipeline (retrieval, optional LLM
calls) instead of the deterministic mock in `runner.default_simulated_executor`.

Design notes:
- Heavy clients (VectorStore, EmbeddingClient, LLMClient, CrossEncoderReranker,
  BM25Retriever, parsed-papers cache) are built once per scenario via an
  internal context object, not per-variant, to keep wall-clock down.
- Retrieval-only scenarios (rerank, hybrid, chunk) skip the LLM-generation
  step of `paper_qa.answer_question` to avoid burning tokens for metrics
  that do not depend on the answer text.
- query_optimization uses the LLM for variant B's query rewrite.
- prompt_comparison uses the LLM via note_generator for each of 9 papers
  with the two prompt templates.

Section matching against `supporting_sections` is case-insensitive.
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

logger = logging.getLogger(__name__)

DATASET_PATH = Path("app/evaluation/datasets/qa_eval_seed.jsonl")
METADATA_DIR = Path("app/storage/metadata")


def _load_dataset(path: Path = DATASET_PATH) -> list[dict]:
    samples: list[dict] = []
    if not path.exists():
        return samples
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            samples.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return samples


def _normalize_sections(secs: list[str] | None) -> set[str]:
    return {s.strip().lower() for s in (secs or []) if s}


def _score_retrieval(
    sample: dict, sources: list[dict], top_k: int = 5
) -> tuple[float, float]:
    """Return (hit@top_k, RR) using paper_id match + case-insensitive section match."""
    paper_id = sample.get("paper_id")
    expected = _normalize_sections(sample.get("supporting_sections"))
    for rank, src in enumerate(sources[:top_k], start=1):
        if src.get("paper_id") != paper_id:
            continue
        sec = (src.get("section") or "").strip().lower()
        if sec and sec in expected:
            return 1.0, 1.0 / rank
    return 0.0, 0.0


@dataclass
class RealScenarioContext:
    samples: list[dict]
    vector_store: Any = None
    embedding_client: Any = None
    llm_client: Any = None
    bm25: Any = None
    cross_encoder: Any = None

    def ensure_basic(self) -> None:
        from app.services.embedding_client import EmbeddingClient
        from app.services.vector_store import VectorStore

        if self.vector_store is None:
            self.vector_store = VectorStore()
        if self.embedding_client is None:
            self.embedding_client = EmbeddingClient()

    def ensure_llm(self) -> None:
        from app.services.llm_client import LLMClient

        if self.llm_client is None:
            self.llm_client = LLMClient()

    def ensure_bm25(self) -> None:
        from app.services.bm25_retriever import BM25Retriever

        self.ensure_basic()
        if self.bm25 is None:
            self.bm25 = BM25Retriever(self.vector_store)

    def ensure_cross_encoder(self) -> None:
        from app.services.reranker import CrossEncoderReranker

        if self.cross_encoder is None:
            # device=None lets sentence-transformers auto-select GPU when available.
            # Embedding stays on CPU (via EMBEDDING_DEVICE env or settings) to avoid VRAM contention.
            self.cross_encoder = CrossEncoderReranker()


def _vector_search(
    ctx: RealScenarioContext, question: str, paper_id: str | None, top_k: int
) -> list[dict]:
    qe = ctx.embedding_client.embed_query(question)
    return ctx.vector_store.query(qe, top_k=top_k, paper_id=paper_id)


def _executor_rerank(ctx: RealScenarioContext):
    from app.services.reranker import CrossEncoderReranker

    ctx.ensure_basic()
    samples = ctx.samples

    def run(variant) -> dict[str, float]:
        params = variant.parameters or {}
        reranker_name = params.get("reranker", "none")
        recall_top_k = int(params.get("recall_top_k", 5))
        final_top_k = int(params.get("final_top_k", 5))

        reranker = None
        if reranker_name == "cross_encoder":
            ctx.ensure_cross_encoder()
            reranker = ctx.cross_encoder

        hits = []
        rrs = []
        retrieval_times = []
        for s in samples:
            t0 = time.perf_counter()
            results = _vector_search(
                ctx, s["question"], s.get("paper_id"), recall_top_k
            )
            if reranker is not None and results:
                results = reranker.rerank(
                    question=s["question"], results=results, top_k=final_top_k
                )
            else:
                results = results[:final_top_k]
            retrieval_times.append(time.perf_counter() - t0)
            hit, rr = _score_retrieval(s, results, top_k=final_top_k)
            hits.append(hit)
            rrs.append(rr)
        n = len(samples)
        return {
            "hit_at_5": sum(hits) / n if n else 0.0,
            "mrr": sum(rrs) / n if n else 0.0,
            "retrieval_time": (sum(retrieval_times) / n) if n else 0.0,
        }

    return run


def _executor_hybrid(ctx: RealScenarioContext):
    from app.services.hybrid_retriever import HybridRetriever

    ctx.ensure_basic()
    samples = ctx.samples

    def run(variant) -> dict[str, float]:
        params = variant.parameters or {}
        retriever_name = params.get("retriever", "vector")
        alpha = float(params.get("alpha", 0.5))
        top_k = int(params.get("top_k", 5))

        if retriever_name == "hybrid":
            ctx.ensure_bm25()
            retriever = HybridRetriever(
                vector_store=ctx.vector_store,
                embedding_client=ctx.embedding_client,
                bm25_retriever=ctx.bm25,
                alpha=alpha,
                recall_top_k=20,
            )

            def do_search(question, paper_id):
                return retriever.search(question, top_k=top_k, paper_id=paper_id)

        else:

            def do_search(question, paper_id):
                return _vector_search(ctx, question, paper_id, top_k)

        hits = []
        rrs = []
        retrieval_times = []
        for s in samples:
            t0 = time.perf_counter()
            results = do_search(s["question"], s.get("paper_id"))
            retrieval_times.append(time.perf_counter() - t0)
            hit, rr = _score_retrieval(s, results, top_k=top_k)
            hits.append(hit)
            rrs.append(rr)
        n = len(samples)
        return {
            "hit_at_5": sum(hits) / n if n else 0.0,
            "mrr": sum(rrs) / n if n else 0.0,
            "retrieval_time": (sum(retrieval_times) / n) if n else 0.0,
        }

    return run


def _executor_query_optimization(ctx: RealScenarioContext):
    from app.services.query_rewriter import QueryRewriter

    ctx.ensure_basic()
    samples = ctx.samples

    def run(variant) -> dict[str, float]:
        params = variant.parameters or {}
        strategy = params.get("query_strategy", "original")
        top_k = int(params.get("top_k", 5))

        rewriter = None
        if strategy == "llm_rewrite":
            ctx.ensure_llm()
            rewriter = QueryRewriter(ctx.llm_client)

        hits = []
        rrs = []
        latencies = []
        for s in samples:
            t0 = time.perf_counter()
            question = s["question"]
            if rewriter is not None:
                question = rewriter.rewrite(question)
            results = _vector_search(ctx, question, s.get("paper_id"), top_k)
            latencies.append(time.perf_counter() - t0)
            hit, rr = _score_retrieval(s, results, top_k=top_k)
            hits.append(hit)
            rrs.append(rr)
        n = len(samples)
        return {
            "hit_at_5": sum(hits) / n if n else 0.0,
            "mrr": sum(rrs) / n if n else 0.0,
            "latency": (sum(latencies) / n) if n else 0.0,
        }

    return run


def _executor_hyde(ctx: RealScenarioContext):
    from app.services.hyde import HyDE

    ctx.ensure_basic()
    ctx.ensure_llm()
    samples = ctx.samples

    def run(variant) -> dict[str, float]:
        params = variant.parameters or {}
        retriever_name = params.get("retriever", "vector")
        top_k = int(params.get("top_k", 5))

        if retriever_name == "hyde":
            hyde_retriever = HyDE(
                llm_client=ctx.llm_client,
                embedding_client=ctx.embedding_client,
                vector_store=ctx.vector_store,
            )

            def do_search(question, paper_id):
                return hyde_retriever.search(question, top_k=top_k, paper_id=paper_id)

        else:

            def do_search(question, paper_id):
                return _vector_search(ctx, question, paper_id, top_k)

        hits = []
        rrs = []
        retrieval_times = []
        for s in samples:
            t0 = time.perf_counter()
            results = do_search(s["question"], s.get("paper_id"))
            retrieval_times.append(time.perf_counter() - t0)
            hit, rr = _score_retrieval(s, results, top_k=top_k)
            hits.append(hit)
            rrs.append(rr)
        n = len(samples)
        return {
            "hit_at_5": sum(hits) / n if n else 0.0,
            "mrr": sum(rrs) / n if n else 0.0,
            "retrieval_time": (sum(retrieval_times) / n) if n else 0.0,
        }

    return run


def _executor_chunk(ctx: RealScenarioContext):
    """Chunk A/B: build an in-memory index per variant and run paper-scoped
    retrieval over the 168 samples. Uses hit@3 to match scenario metric_keys.
    Index lives only inside this executor, the persistent vector store is left untouched.
    """
    import numpy as np

    from app.schemas import PaperParseResult, Section
    from app.services.chunker import chunk_paper
    from app.services.pdf_parser import load_parsed_result

    ctx.ensure_basic()
    samples = ctx.samples

    parsed_cache: dict[str, PaperParseResult] = {}
    for path in sorted(METADATA_DIR.glob("paper_*_parsed.json")):
        paper_id = path.name.removesuffix("_parsed.json")
        try:
            data = load_parsed_result(paper_id, str(METADATA_DIR))
        except Exception as exc:
            logger.warning("Skipping %s: %s", paper_id, exc)
            continue
        sections = [Section(**s) for s in (data.get("sections") or [])]
        parsed_cache[paper_id] = PaperParseResult(
            paper_id=paper_id,
            title=data.get("title", ""),
            abstract=data.get("abstract", ""),
            sections=sections,
            full_text=data.get("full_text", ""),
            pdf_path=data.get("pdf_path", ""),
        )

    def run(variant) -> dict[str, float]:
        params = variant.parameters or {}
        chunk_size = int(params.get("chunk_size", 800))
        overlap = int(params.get("chunk_overlap", 100))
        top_k = 3

        index_start = time.perf_counter()
        all_chunks: list[dict] = []
        for parsed in parsed_cache.values():
            for ck in chunk_paper(parsed, chunk_size=chunk_size, chunk_overlap=overlap):
                all_chunks.append(
                    {
                        "paper_id": ck.paper_id,
                        "title": ck.title,
                        "section": ck.section,
                        "content": ck.content,
                        "chunk_id": ck.chunk_id,
                    }
                )
        if not all_chunks:
            return {"chunk_count": 0.0, "hit_at_3": 0.0, "indexing_time": 0.0}

        embs = ctx.embedding_client.embed_texts([c["content"] for c in all_chunks])
        chunk_emb = np.asarray(embs, dtype=np.float32)
        indexing_seconds = time.perf_counter() - index_start

        query_emb = np.asarray(
            ctx.embedding_client.embed_texts([s["question"] for s in samples]),
            dtype=np.float32,
        )
        qn = query_emb / (np.linalg.norm(query_emb, axis=1, keepdims=True) + 1e-12)
        cn = chunk_emb / (np.linalg.norm(chunk_emb, axis=1, keepdims=True) + 1e-12)
        sim = qn @ cn.T

        hits = []
        for i, s in enumerate(samples):
            paper_id = s.get("paper_id")
            paper_idx = [
                j for j, c in enumerate(all_chunks) if c["paper_id"] == paper_id
            ]
            if not paper_idx:
                hits.append(0.0)
                continue
            ranked = sorted(paper_idx, key=lambda j: -sim[i, j])[:top_k]
            expected = _normalize_sections(s.get("supporting_sections"))
            got = 0.0
            for j in ranked:
                sec = (all_chunks[j]["section"] or "").strip().lower()
                if sec and sec in expected:
                    got = 1.0
                    break
            hits.append(got)

        n = len(samples)
        return {
            "chunk_count": float(len(all_chunks)),
            "hit_at_3": sum(hits) / n if n else 0.0,
            "indexing_time": round(indexing_seconds, 2),
        }

    return run


def _executor_prompt(ctx: RealScenarioContext):
    """Prompt A/B: for each of 9 papers, generate a note with the configured
    prompt template, measure generation_time / content_length / section_coverage.
    """
    from importlib import import_module

    from app.services.pdf_parser import load_parsed_result

    ctx.ensure_llm()

    paper_ids = sorted(
        {
            p.name.removesuffix("_parsed.json")
            for p in METADATA_DIR.glob("paper_*_parsed.json")
        }
    )

    def _generate_with_prompt(paper_id: str, prompt_module: str) -> tuple[float, str]:
        from app.services.note_generator import _build_paper_content

        parsed = load_parsed_result(paper_id, str(METADATA_DIR))
        content = _build_paper_content(parsed)
        title = parsed.get("title", "未知标题")

        module = import_module(prompt_module)
        if hasattr(module, "build_note_prompt"):
            prompt = module.build_note_prompt(title, content)
        elif hasattr(module, "build_note_prompt_compact"):
            prompt = module.build_note_prompt_compact(title, content)
        else:
            raise RuntimeError(f"Prompt module {prompt_module} has no build_* function")

        t0 = time.perf_counter()
        markdown = ctx.llm_client.generate_text(prompt)
        elapsed = time.perf_counter() - t0
        return elapsed, markdown or ""

    def _count_sections(markdown: str) -> int:
        count = 0
        for line in markdown.splitlines():
            stripped = line.strip()
            if stripped.startswith("## ") and not stripped.startswith("### "):
                count += 1
        return count

    def run(variant) -> dict[str, float]:
        params = variant.parameters or {}
        prompt_module = params.get("prompt_module", "app.prompts.paper_note_prompt")
        expected_sections = int(params.get("expected_sections", 13))

        generation_times = []
        content_lengths = []
        coverages = []
        for pid in paper_ids:
            try:
                elapsed, markdown = _generate_with_prompt(pid, prompt_module)
            except Exception as exc:
                logger.warning("note generation failed for %s: %s", pid, exc)
                continue
            generation_times.append(elapsed)
            content_lengths.append(len(markdown))
            found = _count_sections(markdown)
            coverages.append(min(found, expected_sections) / max(1, expected_sections))

        n = max(1, len(generation_times))
        return {
            "generation_time": sum(generation_times) / n,
            "content_length": sum(content_lengths) / n,
            "section_coverage": sum(coverages) / n,
        }

    return run


_DISPATCH: dict[str, Callable[[RealScenarioContext], Callable]] = {
    "rerank_comparison": _executor_rerank,
    "hybrid_comparison": _executor_hybrid,
    "hyde_comparison": _executor_hyde,
    "query_optimization": _executor_query_optimization,
    "chunk_comparison": _executor_chunk,
    "prompt_comparison": _executor_prompt,
}


def make_real_executor(scenario_name: str) -> Callable:
    """Return a `variant_fn(variant) -> dict[str, float]` for the given scenario.

    Raises KeyError if no real executor is registered for the scenario.
    """
    if scenario_name not in _DISPATCH:
        raise KeyError(
            f"No real executor registered for scenario '{scenario_name}'. "
            f"Available: {sorted(_DISPATCH)}"
        )
    samples = _load_dataset()
    ctx = RealScenarioContext(samples=samples)
    return _DISPATCH[scenario_name](ctx)
