"""Embedding性能测试 - 测试向量化速度"""
import sys
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

import time
from statistics import mean, median, stdev

import pytest

from app.services.embedding_client import EmbeddingClient


class TestEmbeddingPerformance:
    """测试embedding client的性能"""

    @pytest.fixture
    def embedding_client(self):
        return EmbeddingClient()

    @pytest.fixture
    def sample_texts(self):
        """不同长度的测试文本"""
        return {
            "short": "深度学习" * 10,  # ~20 tokens
            "medium": "深度学习是机器学习的一个分支" * 50,  # ~200 tokens
            "long": "Transformer模型通过自注意力机制实现了并行计算" * 100,  # ~500 tokens
        }

    def test_single_query_latency(self, embedding_client, sample_texts):
        """测试单次查询延迟"""
        results = {}
        for length, text in sample_texts.items():
            latencies = []
            for _ in range(10):  # 运行10次取平均
                start = time.perf_counter()
                embedding_client.embed_query(text)
                latency = (time.perf_counter() - start) * 1000  # 转为毫秒
                latencies.append(latency)

            results[length] = {
                "mean": mean(latencies),
                "median": median(latencies),
                "std": stdev(latencies),
                "p95": sorted(latencies)[int(len(latencies) * 0.95)],
            }

        # 打印结果
        print("\n=== Embedding Latency ===")
        for length, metrics in results.items():
            print(f"{length:8s}: mean={metrics['mean']:.2f}ms, "
                  f"p95={metrics['p95']:.2f}ms, std={metrics['std']:.2f}ms")

        # 断言：短文本应该在100ms内
        assert results["short"]["p95"] < 100, "短文本embedding太慢"

    def test_batch_throughput(self, embedding_client):
        """测试批量吞吐量"""
        texts = ["这是测试文本" + str(i) for i in range(100)]

        start = time.perf_counter()
        for text in texts:
            embedding_client.embed_query(text)
        duration = time.perf_counter() - start

        throughput = len(texts) / duration
        print(f"\n=== Embedding Throughput ===")
        print(f"处理{len(texts)}条文本，耗时{duration:.2f}s")
        print(f"吞吐量: {throughput:.2f} texts/sec")

        # 断言：应该能达到 >5 texts/sec
        assert throughput > 5, f"吞吐量太低: {throughput:.2f} texts/sec"

    def test_cold_start_vs_warm(self, embedding_client, sample_texts):
        """测试冷启动 vs 热启动"""
        text = sample_texts["medium"]

        # 冷启动
        start = time.perf_counter()
        embedding_client.embed_query(text)
        cold_latency = (time.perf_counter() - start) * 1000

        # 热启动（运行5次）
        warm_latencies = []
        for _ in range(5):
            start = time.perf_counter()
            embedding_client.embed_query(text)
            warm_latencies.append((time.perf_counter() - start) * 1000)

        warm_latency = mean(warm_latencies)

        print(f"\n=== Cold Start vs Warm ===")
        print(f"冷启动: {cold_latency:.2f}ms")
        print(f"热启动: {warm_latency:.2f}ms")
        print(f"加速比: {cold_latency / warm_latency:.2f}x")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
