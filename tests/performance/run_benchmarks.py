"""性能基准测试运行脚本 - 一键运行所有性能测试并生成报告"""
import subprocess
import json
import time
from pathlib import Path
from datetime import datetime


def run_performance_tests():
    """运行所有性能测试并收集结果"""

    print("=" * 60)
    print("ResearchAgent 性能基准测试")
    print("=" * 60)
    print(f"开始时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()

    test_files = [
        ("Embedding性能", "tests/performance/test_embedding_perf.py"),
        ("向量存储性能", "tests/performance/test_vector_store_perf.py"),
        ("QA端到端性能", "tests/performance/test_qa_e2e_perf.py"),
        ("压力测试", "tests/performance/test_stress.py"),
    ]

    results = {}

    for name, test_file in test_files:
        print(f"\n{'=' * 60}")
        print(f"运行: {name}")
        print(f"{'=' * 60}")

        start = time.time()
        try:
            result = subprocess.run(
                ["python", "-m", "pytest", test_file, "-v", "-s", "--tb=short"],
                capture_output=True,
                text=True,
                timeout=600,  # 10分钟超时
            )
            duration = time.time() - start

            results[name] = {
                "status": "PASSED" if result.returncode == 0 else "FAILED",
                "duration": duration,
                "stdout": result.stdout,
                "stderr": result.stderr,
            }

            print(result.stdout)
            if result.stderr:
                print("错误输出:", result.stderr)

            print(f"\n{name} - {results[name]['status']} (耗时: {duration:.2f}s)")

        except subprocess.TimeoutExpired:
            results[name] = {
                "status": "TIMEOUT",
                "duration": 600,
            }
            print(f"{name} - TIMEOUT (超过10分钟)")
        except Exception as e:
            results[name] = {
                "status": "ERROR",
                "error": str(e),
            }
            print(f"{name} - ERROR: {e}")

    # 生成汇总报告
    print("\n" + "=" * 60)
    print("性能测试汇总报告")
    print("=" * 60)

    for name, result in results.items():
        status_symbol = "✓" if result["status"] == "PASSED" else "✗"
        duration = result.get("duration", 0)
        print(f"{status_symbol} {name:20s} - {result['status']:8s} ({duration:.2f}s)")

    total_time = sum(r.get("duration", 0) for r in results.values())
    passed = sum(1 for r in results.values() if r["status"] == "PASSED")
    total = len(results)

    print(f"\n总计: {passed}/{total} 通过")
    print(f"总耗时: {total_time:.2f}s")
    print(f"结束时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    # 保存结果到JSON
    output_dir = Path("tests/performance/results")
    output_dir.mkdir(exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = output_dir / f"benchmark_{timestamp}.json"

    with open(output_file, "w", encoding="utf-8") as f:
        json.dump({
            "timestamp": timestamp,
            "results": results,
            "summary": {
                "passed": passed,
                "total": total,
                "total_time": total_time,
            }
        }, f, indent=2, ensure_ascii=False)

    print(f"\n详细结果已保存到: {output_file}")

    return passed == total


if __name__ == "__main__":
    success = run_performance_tests()
    exit(0 if success else 1)
