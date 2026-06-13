"""性能快速检查 - 热启动版本（预加载模型）"""
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
from app.schemas import Chunk
import tempfile


def warm_benchmark():
    """热启动性能检查 - 预加载模型后测试真实性能"""

    print("🔥 ResearchAgent 性能检查（热启动 - 真实性能）")
    print("=" * 60)

    # 预热：提前加载模型
    print("\n🔄 预热中：加载Embedding模型...")
    embedding_client = EmbeddingClient()
    warmup_start = time.perf_counter()
    embedding_client.embed_query("warmup")  # 触发模型加载
    warmup_time = time.perf_counter() - warmup_start
    print(f"   ✓ 模型加载完成，耗时: {warmup_time:.2f}s")

    print("\n" + "=" * 60)
    print("开始真实性能测试\n")

    # 1. Embedding性能（热启动）
    print("1️⃣  测试Embedding性能（热启动）...")

    text = "深度学习是机器学习的一个分支" * 10
    latencies = []
    for _ in range(10):  # 多测几次取平均
        start = time.perf_counter()
        embedding_client.embed_query(text)
        latencies.append((time.perf_counter() - start) * 1000)

    emb_avg = sum(latencies) / len(latencies)
    emb_min = min(latencies)
    emb_max = max(latencies)
    print(f"   ✓ 平均延迟: {emb_avg:.2f}ms")
    print(f"   ✓ 最快: {emb_min:.2f}ms, 最慢: {emb_max:.2f}ms")

    if emb_avg > 200:
        print(f"   ⚠️  警告：延迟较高（目标<100ms）")
    else:
        print(f"   ✅ 性能优秀！")

    # 2. 批量Embedding测试
    print("\n2️⃣  测试批量Embedding性能...")
    texts = [f"测试文本{i}" for i in range(50)]

    start = time.perf_counter()
    for text in texts:
        embedding_client.embed_query(text)
    duration = time.perf_counter() - start

    throughput = len(texts) / duration
    print(f"   ✓ 处理{len(texts)}条文本，耗时{duration:.2f}s")
    print(f"   ✓ 吞吐量: {throughput:.2f} texts/sec")

    # 3. 向量存储性能
    print("\n3️⃣  测试向量存储性能...")

    with tempfile.TemporaryDirectory() as tmpdir:
        vector_store = VectorStore(persist_dir=tmpdir)

        # 插入100个chunks
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
        start = time.perf_counter()
        vector_store.add_chunks(chunks, embeddings)
        index_time = time.perf_counter() - start

        print(f"   ✓ 索引100个chunks: {index_time:.2f}s")

        # 查询性能
        query_emb = embedding_client.embed_query("测试查询")
        latencies = []
        for _ in range(10):
            start = time.perf_counter()
            vector_store.query(query_emb, top_k=5)
            latencies.append((time.perf_counter() - start) * 1000)

        query_avg = sum(latencies) / len(latencies)
        print(f"   ✓ 向量查询平均延迟: {query_avg:.2f}ms")

    # 4. 端到端QA性能（热启动）
    print("\n4️⃣  测试QA端到端性能（热启动）...")

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

        # 先运行一次预热LLM
        print("   🔄 预热LLM...")
        answer_question(
            question=question,
            vector_store=vector_store,
            embedding_client=embedding_client,
            llm_client=llm_client,
            top_k=3,
        )

        # 正式测试
        print("   🔄 开始QA性能测试...")
        for i in range(3):
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
            print(f"   ✓ 第{i+1}次: {latency:.2f}ms")

        qa_avg = sum(latencies) / len(latencies)
        print(f"\n   ✓ QA端到端平均延迟: {qa_avg:.2f}ms")
        print(f"   ✓ 答案示例: {result['answer'][:50]}...")

        if qa_avg > 2000:
            print(f"   ⚠️  警告：延迟较高（目标<2000ms）")
        else:
            print(f"   ✅ 性能达标！")

    # 总结
    print("\n" + "=" * 60)
    print("📊 热启动性能检查完成\n")

    all_good = emb_avg < 200 and query_avg < 500 and qa_avg < 2000

    if all_good:
        print("✅ 所有指标正常")
    else:
        print("⚠️  部分指标超过目标值")

    print("\n🔥 热启动性能指标（真实运行性能）:")
    print(f"  • Embedding延迟:  {emb_avg:7.2f}ms  {'✅' if emb_avg < 200 else '⚠️'}")
    print(f"  • Embedding吞吐:  {throughput:7.2f} texts/sec")
    print(f"  • 向量查询延迟:   {query_avg:7.2f}ms  {'✅' if query_avg < 500 else '⚠️'}")
    print(f"  • QA端到端延迟:   {qa_avg:7.2f}ms  {'✅' if qa_avg < 2000 else '⚠️'}")

    print(f"\n💡 模型加载（冷启动）: {warmup_time:.2f}s （一次性成本）")

    print("\n" + "=" * 60)
    print("面试话术：")
    print(f"\"系统冷启动需要{warmup_time:.2f}s加载模型（一次性），")
    print(f" 热启动后Embedding延迟{emb_avg:.2f}ms，QA P50延迟{qa_avg:.2f}ms，")
    print(f" 向量查询{query_avg:.2f}ms，整体性能{'达标' if all_good else '需要优化'}。\"")
    print("=" * 60)

    return all_good


if __name__ == "__main__":
    try:
        success = warm_benchmark()
        exit(0 if success else 1)
    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        exit(1)
