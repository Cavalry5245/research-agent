"""向量检索性能测试 - 测试Chroma查询速度和可扩展性"""
import sys
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

import time
from statistics import mean, median
import pytest
import numpy as np
from app.services.vector_store import VectorStore
from app.services.embedding_client import EmbeddingClient


class TestVectorStorePerformance:
    """测试向量数据库的性能"""

    @pytest.fixture
    def vector_store(self, tmp_path):
        """临时vector store"""
        return VectorStore(persist_dir=str(tmp_path / "test_chroma"))

    @pytest.fixture
    def embedding_client(self):
        return EmbeddingClient()

    def _generate_fake_chunks(self, count: int) -> list[dict]:
        """生成测试数据"""
        chunks = []
        for i in range(count):
            chunks.append({
                "paper_id": f"paper_{i % 10}",  # 10篇论文
                "title": f"Test Paper {i % 10}",
                "section": f"Section {i % 5}",
                "content": f"This is test content {i} " * 50,  # ~250 tokens
                "chunk_id": f"chunk_{i}",
                "page_number": i % 20,
            })
        return chunks

    def test_indexing_speed(self, vector_store, embedding_client):
        """测试索引速度 - 关键指标：能否快速建立索引"""
        chunk_counts = [100, 500, 1000]
        results = {}

        for count in chunk_counts:
            chunks = self._generate_fake_chunks(count)

            # 生成embeddings
            embeddings = [embedding_client.embed_query(c["content"]) for c in chunks]

            # 测试索引时间
            start = time.perf_counter()
            for chunk, emb in zip(chunks, embeddings):
                vector_store.add_chunk(
                    paper_id=chunk["paper_id"],
                    chunk_id=chunk["chunk_id"],
                    embedding=emb,
                    metadata=chunk,
                )
            duration = time.perf_counter() - start

            results[count] = {
                "total_time": duration,
                "per_chunk": duration / count * 1000,  # ms per chunk
                "throughput": count / duration,  # chunks/sec
            }

        print("\n=== Indexing Performance ===")
        for count, metrics in results.items():
            print(f"{count:5d} chunks: {metrics['total_time']:.2f}s, "
                  f"{metrics['per_chunk']:.2f}ms/chunk, "
                  f"{metrics['throughput']:.2f} chunks/sec")

        # 断言：1000 chunks应该在1分钟内完成
        assert results[1000]["total_time"] < 60, "索引太慢"

    def test_query_latency_by_db_size(self, vector_store, embedding_client):
        """测试不同数据规模下的查询延迟"""
        db_sizes = [100, 500, 1000, 5000]
        results = {}

        for size in db_sizes:
            # 准备数据
            chunks = self._generate_fake_chunks(size)
            embeddings = [embedding_client.embed_query(c["content"]) for c in chunks]
            for chunk, emb in zip(chunks, embeddings):
                vector_store.add_chunk(
                    paper_id=chunk["paper_id"],
                    chunk_id=chunk["chunk_id"],
                    embedding=emb,
                    metadata=chunk,
                )

            # 测试查询延迟
            query_emb = embedding_client.embed_query("test query")
            latencies = []
            for _ in range(10):  # 10次查询
                start = time.perf_counter()
                vector_store.query(query_emb, top_k=5)
                latency = (time.perf_counter() - start) * 1000
                latencies.append(latency)

            results[size] = {
                "mean": mean(latencies),
                "median": median(latencies),
                "p95": sorted(latencies)[int(len(latencies) * 0.95)],
            }

        print("\n=== Query Latency by DB Size ===")
        for size, metrics in results.items():
            print(f"{size:6d} chunks: mean={metrics['mean']:.2f}ms, "
                  f"p95={metrics['p95']:.2f}ms")

        # 断言：5000 chunks的p95延迟应该<500ms
        assert results[5000]["p95"] < 500, "大规模查询太慢"

    def test_concurrent_queries(self, vector_store, embedding_client):
        """测试并发查询性能"""
        import concurrent.futures

        # 准备数据
        chunks = self._generate_fake_chunks(1000)
        embeddings = [embedding_client.embed_query(c["content"]) for c in chunks]
        for chunk, emb in zip(chunks, embeddings):
            vector_store.add_chunk(
                paper_id=chunk["paper_id"],
                chunk_id=chunk["chunk_id"],
                embedding=emb,
                metadata=chunk,
            )

        # 并发查询
        query_emb = embedding_client.embed_query("test query")
        num_workers = [1, 2, 4, 8]
        results = {}

        for workers in num_workers:
            def run_query(_):
                return vector_store.query(query_emb, top_k=5)

            start = time.perf_counter()
            with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as executor:
                list(executor.map(run_query, range(100)))  # 100次查询
            duration = time.perf_counter() - start

            results[workers] = {
                "total_time": duration,
                "qps": 100 / duration,
            }

        print("\n=== Concurrent Query Performance ===")
        for workers, metrics in results.items():
            print(f"{workers} workers: {metrics['total_time']:.2f}s, "
                  f"QPS={metrics['qps']:.2f}")

        # 断言：4个worker应该比1个快
        assert results[4]["qps"] > results[1]["qps"] * 1.5, "并发加速不明显"

    def test_memory_usage(self, vector_store, embedding_client):
        """测试内存占用"""
        import psutil
        import os

        process = psutil.Process(os.getpid())

        # 记录初始内存
        mem_before = process.memory_info().rss / 1024 / 1024  # MB

        # 插入5000个chunks
        chunks = self._generate_fake_chunks(5000)
        embeddings = [embedding_client.embed_query(c["content"]) for c in chunks]
        for chunk, emb in zip(chunks, embeddings):
            vector_store.add_chunk(
                paper_id=chunk["paper_id"],
                chunk_id=chunk["chunk_id"],
                embedding=emb,
                metadata=chunk,
            )

        # 记录最终内存
        mem_after = process.memory_info().rss / 1024 / 1024  # MB
        mem_increase = mem_after - mem_before

        print(f"\n=== Memory Usage ===")
        print(f"初始内存: {mem_before:.2f} MB")
        print(f"5000 chunks后: {mem_after:.2f} MB")
        print(f"增长: {mem_increase:.2f} MB ({mem_increase / 5000:.2f} MB/chunk)")

        # 断言：5000 chunks应该<500MB增长
        assert mem_increase < 500, f"内存增长太大: {mem_increase:.2f}MB"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
