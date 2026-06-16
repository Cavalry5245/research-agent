#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Quick HyDE test with 10 samples only.

This is a faster validation to ensure the experiment framework works
before running the full 168-sample experiment.
"""
import sys
import os
import json
import time
from pathlib import Path

if sys.platform == "win32":
    os.system("chcp 65001 >nul 2>&1")
    sys.stdout.reconfigure(encoding='utf-8')

sys.path.insert(0, str(Path(__file__).parent))


def main():
    print("=" * 80)
    print("HyDE Quick Test (10 samples)")
    print("=" * 80)
    print()

    # Load 10 samples (skip paper_20260509_004 which is not in vector store)
    from app.experiments.real_executors import _load_dataset, RealScenarioContext

    all_samples = _load_dataset()
    samples = [s for s in all_samples if s.get('paper_id') != 'paper_20260509_004'][:10]
    print(f"Loaded {len(samples)} samples (skipped paper_20260509_004)")
    print()

    # Test Vector baseline
    print("Running Variant A: Vector (baseline)...")
    ctx = RealScenarioContext(samples=samples)
    ctx.ensure_basic()

    from app.experiments.real_executors import _vector_search, _score_retrieval

    hits_a = []
    times_a = []
    for s in samples:
        t0 = time.perf_counter()
        results = _vector_search(ctx, s["question"], s.get("paper_id"), top_k=5)
        times_a.append(time.perf_counter() - t0)
        hit, rr = _score_retrieval(s, results, top_k=5)
        hits_a.append(hit)

    print(f"  hit@5 = {sum(hits_a)/len(hits_a):.4f}")
    print(f"  avg time = {sum(times_a)/len(times_a):.4f}s")
    print()

    # Test HyDE
    print("Running Variant B: HyDE...")
    ctx.ensure_llm()

    from app.services.hyde import HyDE

    hyde = HyDE(
        llm_client=ctx.llm_client,
        embedding_client=ctx.embedding_client,
        vector_store=ctx.vector_store,
    )

    hits_b = []
    times_b = []
    for i, s in enumerate(samples):
        print(f"  [{i+1}/{len(samples)}] Processing: {s['question'][:50]}...")
        t0 = time.perf_counter()
        results = hyde.search(s["question"], top_k=5, paper_id=s.get("paper_id"))
        elapsed = time.perf_counter() - t0
        times_b.append(elapsed)
        hit, rr = _score_retrieval(s, results, top_k=5)
        hits_b.append(hit)
        print(f"      hit={int(hit)}, time={elapsed:.2f}s")

    print()
    print(f"  hit@5 = {sum(hits_b)/len(hits_b):.4f}")
    print(f"  avg time = {sum(times_b)/len(times_b):.4f}s")
    print()

    # Compare
    print("=" * 80)
    print("Comparison:")
    print("-" * 80)

    hit_a = sum(hits_a) / len(hits_a)
    hit_b = sum(hits_b) / len(hits_b)
    time_a = sum(times_a) / len(times_a)
    time_b = sum(times_b) / len(times_b)

    print(f"{'Metric':<20s} {'Vector (A)':<15s} {'HyDE (B)':<15s} {'Delta':<15s}")
    print("-" * 80)
    print(f"{'hit@5':<20s} {hit_a:<15.4f} {hit_b:<15.4f} {(hit_b-hit_a):<+15.4f}")
    print(f"{'avg time (s)':<20s} {time_a:<15.4f} {time_b:<15.4f} {(time_b-time_a):<+15.4f}")

    print()
    if hit_b > hit_a:
        print(f"✅ HyDE shows +{(hit_b-hit_a)/hit_a*100:.1f}% improvement on this small sample")
    elif hit_b < hit_a:
        print(f"⚠️  HyDE shows {(hit_b-hit_a)/hit_a*100:.1f}% degradation on this small sample")
    else:
        print("➖ No difference detected")

    print()
    print("Note: This is only 10 samples. Run the full experiment for statistical significance.")
    print("=" * 80)

    return 0


if __name__ == "__main__":
    sys.exit(main())
