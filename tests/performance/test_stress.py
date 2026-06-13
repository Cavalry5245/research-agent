"""压力测试 - 测试系统在高负载下的表现"""
import sys
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

import time
import pytest
from concurrent.futures import ThreadPoolExecutor, as_completed
from app.services.paper_qa import answer_question
from app.services.vector_store import VectorStore
from app.services.embedding_client import EmbeddingClient
from app.services.llm_client import LLMClient


class TestStressPerformance:
    """压力测试 - 找到系统的极限"""

    @pytest.fixture
    def stress_env(self, tmp_path):
        """准备压力测试环境 - 更大规模的数据"""
        vector_store = VectorStore(persist_dir=str(tmp_path / "stress_chroma"))
        embedding_client = EmbeddingClient()
        llm_client = LLMClient()

        # 插入更多数据（模拟10篇论文，每篇10个chunks）
        print("\n准备压力测试数据...")
        for paper_idx in range(10):
            paper_id = f"paper_{paper_idx:03d}"
            for chunk_idx in range(10):
                content = f"这是论文{paper_idx}的第{chunk_idx}个片段。" * 20
                embedding = embedding_client.embed_query(content)
                vector_store.add_chunk(
                    paper_id=paper_id,
                    chunk_id=f"{paper_id}_chunk_{chunk_idx}",
                    embedding=embedding,
                    metadata={
                        "paper_id": paper_id,
                        "title": f"Test Paper {paper_idx}",
                        "section": f"Section {chunk_idx}",
                        "content": content,
                        "chunk_id": f"{paper_id}_chunk_{chunk_idx}",
                    },
                )
        print("数据准备完成：10篇论文，100个chunks")

        return vector_store, embedding_client, llm_client

    def test_max_concurrent_queries(self, stress_env):
        """测试最大并发数 - 找到系统能承受的并发上限"""
        vector_store, embedding_client, llm_client = stress_env

        questions = [f"问题{i}" for i in range(50)]

        results = {}
        for workers in [1, 2, 5, 10, 20]:
            print(f"\n测试 {workers} 并发...")

            def run_qa(question):
                start = time.perf_counter()
                try:
                    answer_question(
                        question=question,
                        vector_store=vector_store,
                        embedding_client=embedding_client,
                        llm_client=llm_client,
                        top_k=3,
                    )
                    latency = (time.perf_counter() - start) * 1000
                    return {"success": True, "latency": latency}
                except Exception as e:
                    return {"success": False, "error": str(e)}

            start = time.perf_counter()
            with ThreadPoolExecutor(max_workers=workers) as executor:
                futures = [executor.submit(run_qa, q) for q in questions]
                outcomes = [f.result() for f in as_completed(futures)]
            total_time = time.perf_counter() - start

            success_count = sum(1 for o in outcomes if o["success"])
            success_latencies = [o["latency"] for o in outcomes if o["success"]]

            results[workers] = {
                "total_time": total_time,
                "success_count": success_count,
                "success_rate": success_count / len(questions),
                "qps": success_count / total_time,
                "avg_latency": sum(success_latencies) / len(success_latencies) if success_latencies else 0,
            }

        print("\n=== Max Concurrent Queries ===")
        for workers, metrics in results.items():
            print(f"{workers:3d} workers: "
                  f"QPS={metrics['qps']:6.2f}, "
                  f"成功率={metrics['success_rate']*100:5.1f}%, "
                  f"平均延迟={metrics['avg_latency']:7.2f}ms")

        # 找到最佳并发数
        best_workers = max(results.items(), key=lambda x: x[1]["qps"])[0]
        print(f"\n最佳并发数: {best_workers} workers (QPS={results[best_workers]['qps']:.2f})")

    def test_sustained_load(self, stress_env):
        """测试持续负载 - 系统能否稳定运行一段时间"""
        vector_store, embedding_client, llm_client = stress_env

        questions = [f"持续负载测试问题{i}" for i in range(100)]

        print("\n开始持续负载测试（60秒）...")
        start_time = time.perf_counter()
        end_time = start_time + 60  # 运行60秒

        completed = 0
        latencies = []

        while time.perf_counter() < end_time:
            question = questions[completed % len(questions)]
            qstart = time.perf_counter()
            try:
                answer_question(
                    question=question,
                    vector_store=vector_store,
                    embedding_client=embedding_client,
                    llm_client=llm_client,
                    top_k=3,
                )
                latency = (time.perf_counter() - qstart) * 1000
                latencies.append(latency)
                completed += 1
            except Exception as e:
                print(f"错误: {e}")

        duration = time.perf_counter() - start_time
        qps = completed / duration

        print(f"\n=== Sustained Load Test ===")
        print(f"运行时间: {duration:.2f}s")
        print(f"完成查询: {completed}")
        print(f"平均QPS: {qps:.2f}")
        print(f"平均延迟: {sum(latencies)/len(latencies):.2f}ms")
        print(f"P95延迟: {sorted(latencies)[int(len(latencies)*0.95)]:.2f}ms")

        # 断言：应该能完成至少30个查询（0.5 QPS）
        assert completed > 30, f"持续负载测试完成数太少: {completed}"

    def test_memory_leak_detection(self, stress_env):
        """测试内存泄漏 - 长时间运行内存是否稳定"""
        import psutil
        import os

        vector_store, embedding_client, llm_client = stress_env
        process = psutil.Process(os.getpid())

        # 记录初始内存
        mem_start = process.memory_info().rss / 1024 / 1024  # MB

        # 运行100次查询
        for i in range(100):
            answer_question(
                question=f"测试问题{i}",
                vector_store=vector_store,
                embedding_client=embedding_client,
                llm_client=llm_client,
                top_k=3,
            )

            # 每10次检查一次内存
            if (i + 1) % 10 == 0:
                mem_current = process.memory_info().rss / 1024 / 1024
                print(f"第{i+1}次查询后内存: {mem_current:.2f} MB")

        # 记录最终内存
        mem_end = process.memory_info().rss / 1024 / 1024
        mem_growth = mem_end - mem_start

        print(f"\n=== Memory Leak Detection ===")
        print(f"初始内存: {mem_start:.2f} MB")
        print(f"最终内存: {mem_end:.2f} MB")
        print(f"增长: {mem_growth:.2f} MB ({mem_growth/100:.2f} MB/query)")

        # 断言：100次查询内存增长应该<100MB
        assert mem_growth < 100, f"疑似内存泄漏: 增长{mem_growth:.2f}MB"

    def test_error_recovery(self, stress_env):
        """测试错误恢复能力"""
        vector_store, embedding_client, llm_client = stress_env

        # 故意制造错误场景
        questions = [
            "正常问题1",
            "",  # 空问题
            "x" * 10000,  # 超长问题
            "正常问题2",
        ]

        results = []
        for question in questions:
            try:
                result = answer_question(
                    question=question,
                    vector_store=vector_store,
                    embedding_client=embedding_client,
                    llm_client=llm_client,
                    top_k=3,
                )
                results.append({"success": True, "result": result})
            except Exception as e:
                results.append({"success": False, "error": str(e)})

        print("\n=== Error Recovery ===")
        for i, (question, result) in enumerate(zip(questions, results)):
            status = "✓" if result["success"] else "✗"
            q_preview = question[:50] if question else "(空)"
            print(f"{status} 问题{i+1}: {q_preview}")

        # 统计成功率
        success_count = sum(1 for r in results if r["success"])
        print(f"\n成功率: {success_count}/{len(questions)} ({success_count/len(questions)*100:.1f}%)")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s", "--tb=short"])
