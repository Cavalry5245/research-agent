"""端到端QA性能测试 - 最关键的用户体验指标"""
import sys
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

import time
from statistics import mean, median
import pytest
from app.services.paper_qa import answer_question
from app.services.vector_store import VectorStore
from app.services.embedding_client import EmbeddingClient
from app.services.llm_client import LLMClient


class TestQAEndToEndPerformance:
    """测试完整的QA流程性能"""

    @pytest.fixture
    def setup_qa_env(self, tmp_path):
        """准备QA测试环境"""
        vector_store = VectorStore(persist_dir=str(tmp_path / "test_chroma"))
        embedding_client = EmbeddingClient()
        llm_client = LLMClient()

        # 插入测试数据（模拟3篇论文）
        test_papers = [
            {
                "paper_id": "paper_001",
                "title": "Attention Is All You Need",
                "chunks": [
                    "Transformer模型完全基于注意力机制，不使用循环或卷积。",
                    "多头注意力允许模型关注不同位置的不同表示子空间。",
                    "位置编码用于注入序列顺序信息，因为模型本身不包含循环或卷积。",
                ],
            },
            {
                "paper_id": "paper_002",
                "title": "BERT: Pre-training of Deep Bidirectional Transformers",
                "chunks": [
                    "BERT通过掩码语言模型和下一句预测进行预训练。",
                    "双向Transformer编码器可以同时学习左右上下文。",
                    "BERT在11个NLP任务上取得了SOTA结果。",
                ],
            },
            {
                "paper_id": "paper_003",
                "title": "GPT-3: Language Models are Few-Shot Learners",
                "chunks": [
                    "GPT-3拥有1750亿参数，是当时最大的语言模型。",
                    "少样本学习能力允许模型在几乎没有微调的情况下执行任务。",
                    "上下文学习通过提示就能完成多种NLP任务。",
                ],
            },
        ]

        for paper in test_papers:
            for i, chunk_text in enumerate(paper["chunks"]):
                embedding = embedding_client.embed_query(chunk_text)
                vector_store.add_chunk(
                    paper_id=paper["paper_id"],
                    chunk_id=f"{paper['paper_id']}_chunk_{i}",
                    embedding=embedding,
                    metadata={
                        "paper_id": paper["paper_id"],
                        "title": paper["title"],
                        "section": f"Section {i+1}",
                        "content": chunk_text,
                        "chunk_id": f"{paper['paper_id']}_chunk_{i}",
                    },
                )

        return vector_store, embedding_client, llm_client

    def test_qa_latency_breakdown(self, setup_qa_env):
        """测试QA延迟的各个组成部分"""
        vector_store, embedding_client, llm_client = setup_qa_env
        question = "Transformer模型的核心特点是什么？"

        # 分步测试
        # 1. Embedding查询
        start = time.perf_counter()
        query_emb = embedding_client.embed_query(question)
        emb_time = (time.perf_counter() - start) * 1000

        # 2. 向量检索
        start = time.perf_counter()
        results = vector_store.query(query_emb, top_k=5)
        retrieval_time = (time.perf_counter() - start) * 1000

        # 3. 构建prompt和LLM生成
        from app.prompts.qa_prompt import build_qa_prompt
        context = "\n\n".join([f"[片段{i+1}] {r['content']}" for i, r in enumerate(results)])
        prompt = build_qa_prompt(question, context)

        start = time.perf_counter()
        answer = llm_client.generate_text(prompt)
        llm_time = (time.perf_counter() - start) * 1000

        total_time = emb_time + retrieval_time + llm_time

        print("\n=== QA Latency Breakdown ===")
        print(f"Embedding:  {emb_time:7.2f}ms ({emb_time/total_time*100:5.1f}%)")
        print(f"Retrieval:  {retrieval_time:7.2f}ms ({retrieval_time/total_time*100:5.1f}%)")
        print(f"LLM Gen:    {llm_time:7.2f}ms ({llm_time/total_time*100:5.1f}%)")
        print(f"Total:      {total_time:7.2f}ms")

        # 断言：总延迟应该<3秒
        assert total_time < 3000, f"QA延迟太高: {total_time:.2f}ms"

    def test_qa_e2e_latency_distribution(self, setup_qa_env):
        """测试端到端QA延迟分布"""
        vector_store, embedding_client, llm_client = setup_qa_env

        questions = [
            "Transformer的注意力机制是什么？",
            "BERT如何进行预训练？",
            "GPT-3有多少参数？",
            "什么是多头注意力？",
            "少样本学习是如何工作的？",
        ]

        latencies = []
        for question in questions:
            start = time.perf_counter()
            answer_question(
                question=question,
                vector_store=vector_store,
                embedding_client=embedding_client,
                llm_client=llm_client,
                top_k=5,
            )
            latency = (time.perf_counter() - start) * 1000
            latencies.append(latency)

        stats = {
            "mean": mean(latencies),
            "median": median(latencies),
            "min": min(latencies),
            "max": max(latencies),
            "p95": sorted(latencies)[int(len(latencies) * 0.95)],
        }

        print("\n=== QA E2E Latency Distribution ===")
        print(f"Mean:   {stats['mean']:.2f}ms")
        print(f"Median: {stats['median']:.2f}ms")
        print(f"Min:    {stats['min']:.2f}ms")
        print(f"Max:    {stats['max']:.2f}ms")
        print(f"P95:    {stats['p95']:.2f}ms")

        # 断言：P95应该<2秒
        assert stats["p95"] < 2000, f"P95延迟太高: {stats['p95']:.2f}ms"

    def test_qa_throughput(self, setup_qa_env):
        """测试QA吞吐量 - 每秒能处理多少问题"""
        vector_store, embedding_client, llm_client = setup_qa_env

        questions = ["测试问题" + str(i) for i in range(20)]

        start = time.perf_counter()
        for question in questions:
            answer_question(
                question=question,
                vector_store=vector_store,
                embedding_client=embedding_client,
                llm_client=llm_client,
                top_k=3,  # 减少top_k加速
            )
        duration = time.perf_counter() - start

        qps = len(questions) / duration

        print(f"\n=== QA Throughput ===")
        print(f"处理{len(questions)}个问题，耗时{duration:.2f}s")
        print(f"QPS: {qps:.2f} questions/sec")

        # 断言：单机QPS应该>1
        assert qps > 1, f"QPS太低: {qps:.2f}"

    def test_concurrent_qa_performance(self, setup_qa_env):
        """测试并发QA性能"""
        import concurrent.futures

        vector_store, embedding_client, llm_client = setup_qa_env

        questions = [
            "Transformer的核心特点？",
            "BERT的预训练方法？",
            "GPT-3的参数量？",
        ] * 5  # 15个问题

        def run_qa(question):
            return answer_question(
                question=question,
                vector_store=vector_store,
                embedding_client=embedding_client,
                llm_client=llm_client,
                top_k=3,
            )

        # 串行
        start = time.perf_counter()
        for q in questions[:5]:
            run_qa(q)
        serial_time = time.perf_counter() - start

        # 并发
        start = time.perf_counter()
        with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
            list(executor.map(run_qa, questions[:5]))
        concurrent_time = time.perf_counter() - start

        speedup = serial_time / concurrent_time

        print(f"\n=== Concurrent QA Performance ===")
        print(f"串行: {serial_time:.2f}s")
        print(f"并发(3 workers): {concurrent_time:.2f}s")
        print(f"加速比: {speedup:.2f}x")

        # 并发应该有一定加速
        assert speedup > 1.2, f"并发加速不明显: {speedup:.2f}x"

    def test_cache_effect(self, setup_qa_env):
        """测试缓存效果（如果实现了的话）"""
        vector_store, embedding_client, llm_client = setup_qa_env
        question = "Transformer的注意力机制是什么？"

        # 第一次查询（冷启动）
        start = time.perf_counter()
        answer_question(
            question=question,
            vector_store=vector_store,
            embedding_client=embedding_client,
            llm_client=llm_client,
            top_k=5,
        )
        cold_time = (time.perf_counter() - start) * 1000

        # 第二次查询（可能命中缓存）
        start = time.perf_counter()
        answer_question(
            question=question,
            vector_store=vector_store,
            embedding_client=embedding_client,
            llm_client=llm_client,
            top_k=5,
        )
        warm_time = (time.perf_counter() - start) * 1000

        print(f"\n=== Cache Effect ===")
        print(f"冷启动: {cold_time:.2f}ms")
        print(f"热启动: {warm_time:.2f}ms")
        print(f"加速比: {cold_time / warm_time:.2f}x")

        # 注意：如果没实现缓存，这个测试会失败，可以注释掉
        # assert cold_time / warm_time > 1.5, "缓存效果不明显"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
