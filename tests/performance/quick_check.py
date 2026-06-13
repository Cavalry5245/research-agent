"""简化的性能快速检查脚本 - 适合日常开发使用"""
import sys
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

import time
from app.services.embedding_client import EmbeddingClient
from app.services.vector_store import VectorStore
from app.services.llm_client import LLMClient
from app.services.paper_qa import answer_question


def quick_benchmark():
    """快速性能检查（<30秒）- 适合PR前快速验证"""

    print("🚀 ResearchAgent 快速性能检查")
    print("=" * 60)

    # 1. Embedding性能
    print("\n1️⃣  测试Embedding性能...")
    embedding_client = EmbeddingClient()

    text = "深度学习是机器学习的一个分支" * 10
    latencies = []
    for _ in range(5):
        start = time.perf_counter()
        embedding_client.embed_query(text)
        latencies.append((time.perf_counter() - start) * 1000)

    emb_avg = sum(latencies) / len(latencies)
    print(f"   ✓ Embedding平均延迟: {emb_avg:.2f}ms")

    if emb_avg > 200:
        print(f"   ⚠️  警告：延迟较高（目标<100ms）")

    # 2. 向量存储性能
    print("\n2️⃣  测试向量存储性能...")
    import tempfile
    from app.schemas import Chunk

    with tempfile.TemporaryDirectory() as tmpdir:
        vector_store = VectorStore(persist_dir=tmpdir)

        # 插入100个chunks
        start = time.perf_counter()
        chunks = []
        embeddings = []
        for i in range(100):
            chunk = Chunk(
                chunk_id=f"chunk_{i}",
                paper_id=f"paper_{i//10}",
                title=f"Test Paper {i//10}",
                section=f"Section {i%5}",
                content=f"测试内容{i}",
                page_number=i % 20,
            )
            chunks.append(chunk)
            embeddings.append(embedding_client.embed_query(f"测试内容{i}"))

        # 批量添加
        vector_store.add_chunks(chunks, embeddings)
        index_time = time.perf_counter() - start

        print(f"   ✓ 索引100个chunks: {index_time:.2f}s ({index_time/100*1000:.2f}ms/chunk)")

        # 查询性能
        query_emb = embedding_client.embed_query("测试查询")
        latencies = []
        for _ in range(5):
            start = time.perf_counter()
            vector_store.query(query_emb, top_k=5)
            latencies.append((time.perf_counter() - start) * 1000)

        query_avg = sum(latencies) / len(latencies)
        print(f"   ✓ 向量查询平均延迟: {query_avg:.2f}ms")

        if query_avg > 500:
            print(f"   ⚠️  警告：查询较慢（目标<500ms）")

    # 3. 端到端QA性能
    print("\n3️⃣  测试QA端到端性能...")
    from app.schemas import Chunk

    with tempfile.TemporaryDirectory() as tmpdir:
        vector_store = VectorStore(persist_dir=tmpdir)
        llm_client = LLMClient()

        # 准备测试数据
        test_chunks_data = [
            "Transformer模型使用自注意力机制进行序列建模。",
            "BERT通过掩码语言模型进行预训练。",
            "GPT-3是一个拥有1750亿参数的大型语言模型。",
        ]

        chunks = []
        embeddings = []
        for i, content in enumerate(test_chunks_data):
            chunk = Chunk(
                chunk_id=f"chunk_{i}",
                paper_id="test_paper",
                title="Test Paper",
                section=f"Section {i}",
                content=content,
                page_number=i + 1,
            )
            chunks.append(chunk)
            embeddings.append(embedding_client.embed_query(content))

        vector_store.add_chunks(chunks, embeddings)

        # QA测试
        question = "Transformer的核心机制是什么？"
        latencies = []

        for _ in range(3):
            start = time.perf_counter()
            result = answer_question(
                question=question,
                vector_store=vector_store,
                embedding_client=embedding_client,
                llm_client=llm_client,
                top_k=3,
            )
            latency = (time.perf_counter() - start) * 1000
            latencies.append(latency)

        qa_avg = sum(latencies) / len(latencies)
        print(f"   ✓ QA端到端平均延迟: {qa_avg:.2f}ms")
        print(f"   ✓ 答案示例: {result['answer'][:50]}...")

        if qa_avg > 2000:
            print(f"   ⚠️  警告：延迟较高（目标<2000ms）")

    # 总结
    print("\n" + "=" * 60)
    print("📊 快速检查完成\n")

    all_good = emb_avg < 200 and query_avg < 500 and qa_avg < 2000

    if all_good:
        print("✅ 所有指标正常")
    else:
        print("⚠️  部分指标超过目标值，建议运行完整性能测试")
        print("   运行命令: python tests/performance/run_benchmarks.py")

    print("\n关键指标:")
    print(f"  • Embedding延迟:  {emb_avg:7.2f}ms  {'✅' if emb_avg < 200 else '⚠️'}")
    print(f"  • 向量查询延迟:   {query_avg:7.2f}ms  {'✅' if query_avg < 500 else '⚠️'}")
    print(f"  • QA端到端延迟:   {qa_avg:7.2f}ms  {'✅' if qa_avg < 2000 else '⚠️'}")

    return all_good


if __name__ == "__main__":
    try:
        success = quick_benchmark()
        exit(0 if success else 1)
    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        exit(1)
