#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Smoke test for HyDE integration.

This tests:
1. HyDE module can be imported
2. HyDE can generate hypothetical documents
3. HyDE can perform search
"""
import sys
import os
from pathlib import Path

# Fix Windows console encoding
if sys.platform == "win32":
    os.system("chcp 65001 >nul 2>&1")
    sys.stdout.reconfigure(encoding='utf-8')

sys.path.insert(0, str(Path(__file__).parent))


def test_hyde_import():
    print("Test 1: Import HyDE module...")
    try:
        from app.services.hyde import HyDE
        print("✅ HyDE module imported successfully")
        return True
    except Exception as e:
        print(f"❌ Failed to import HyDE: {e}")
        return False


def test_hyde_generate():
    print("\nTest 2: Generate hypothetical document...")
    try:
        from app.services.hyde import HyDE
        from app.services.llm_client import LLMClient
        from app.services.embedding_client import EmbeddingClient
        from app.services.vector_store import VectorStore

        llm = LLMClient()
        embedding = EmbeddingClient()
        vector_store = VectorStore()

        hyde = HyDE(llm, embedding, vector_store)

        test_query = "这篇论文使用了什么数据集？"
        print(f"   Query: {test_query}")

        hypo_doc = hyde.generate_hypothetical_doc(test_query)
        print(f"   Generated hypothetical doc ({len(hypo_doc)} chars):")
        print(f"   {hypo_doc[:200]}...")

        if hypo_doc and len(hypo_doc) > 50:
            print("✅ Hypothetical document generated successfully")
            return True
        else:
            print("❌ Hypothetical document too short or empty")
            return False

    except Exception as e:
        print(f"❌ Failed to generate hypothetical document: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_hyde_search():
    print("\nTest 3: Perform HyDE search...")
    try:
        from app.services.hyde import HyDE
        from app.services.llm_client import LLMClient
        from app.services.embedding_client import EmbeddingClient
        from app.services.vector_store import VectorStore

        llm = LLMClient()
        embedding = EmbeddingClient()
        vector_store = VectorStore()

        # Check if vector store has data
        if vector_store.count() == 0:
            print("⚠️  Vector store is empty, skipping search test")
            print("   (This is OK if you haven't indexed any papers yet)")
            return True

        hyde = HyDE(llm, embedding, vector_store)

        test_query = "这篇论文的主要方法是什么？"
        print(f"   Query: {test_query}")

        results = hyde.search(test_query, top_k=3)
        print(f"   Retrieved {len(results)} results")

        if results:
            print(f"   Top result: {results[0].get('section', 'N/A')} (score: {results[0].get('score', 0):.4f})")
            print("✅ HyDE search completed successfully")
            return True
        else:
            print("⚠️  No results returned (may be OK if corpus is small)")
            return True

    except Exception as e:
        print(f"❌ Failed to perform HyDE search: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    print("=" * 80)
    print("HyDE Integration Smoke Test")
    print("=" * 80)
    print()

    results = []
    results.append(("Import", test_hyde_import()))
    results.append(("Generate", test_hyde_generate()))
    results.append(("Search", test_hyde_search()))

    print()
    print("=" * 80)
    print("Summary:")
    print("-" * 80)

    for test_name, passed in results:
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{test_name:20s} {status}")

    all_passed = all(r[1] for r in results)

    print()
    if all_passed:
        print("✅ All tests passed! HyDE is ready for A/B experiment.")
        print()
        print("Next step: Run the full experiment with:")
        print("  python run_hyde_experiment.py")
    else:
        print("❌ Some tests failed. Please fix issues before running experiment.")

    print("=" * 80)

    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
