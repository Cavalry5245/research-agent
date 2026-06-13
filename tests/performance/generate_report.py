"""性能基准测试可视化 - 生成性能报告和图表"""
import json
from pathlib import Path
from datetime import datetime


def generate_markdown_report(benchmark_file: Path):
    """生成Markdown格式的性能报告"""

    with open(benchmark_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    timestamp = data.get("timestamp", "unknown")
    results = data.get("results", {})
    summary = data.get("summary", {})

    # 解析各测试的关键指标
    metrics = extract_metrics_from_results(results)

    # 生成Markdown
    md = []
    md.append(f"# ResearchAgent 性能基准测试报告\n")
    md.append(f"**测试时间**: {datetime.strptime(timestamp, '%Y%m%d_%H%M%S').strftime('%Y-%m-%d %H:%M:%S')}\n")
    md.append(f"**测试环境**: Python 3.10+, {get_system_info()}\n")
    md.append("")

    # 执行摘要
    md.append("## 📊 执行摘要\n")
    md.append(f"- **通过率**: {summary['passed']}/{summary['total']} ({summary['passed']/summary['total']*100:.1f}%)")
    md.append(f"- **总耗时**: {summary['total_time']:.2f}s")
    md.append("")

    # 关键性能指标
    md.append("## 🎯 关键性能指标\n")
    md.append("| 指标 | 值 | 目标 | 状态 |")
    md.append("|------|-----|------|------|")

    # 从metrics中提取关键指标
    if "qa_e2e" in metrics:
        qa = metrics["qa_e2e"]
        md.append(f"| QA P95延迟 | {qa.get('p95_latency', 'N/A')}ms | <2000ms | {'✅' if qa.get('p95_latency', 9999) < 2000 else '❌'} |")
        md.append(f"| QA QPS | {qa.get('qps', 'N/A')} | >1 | {'✅' if qa.get('qps', 0) > 1 else '❌'} |")

    if "embedding" in metrics:
        emb = metrics["embedding"]
        md.append(f"| Embedding延迟 | {emb.get('p95_latency', 'N/A')}ms | <100ms | {'✅' if emb.get('p95_latency', 9999) < 100 else '❌'} |")

    if "vector_store" in metrics:
        vs = metrics["vector_store"]
        md.append(f"| 向量查询延迟 | {vs.get('query_latency', 'N/A')}ms | <500ms | {'✅' if vs.get('query_latency', 9999) < 500 else '❌'} |")

    md.append("")

    # 详细测试结果
    md.append("## 📋 详细测试结果\n")

    for test_name, result in results.items():
        md.append(f"### {test_name}\n")
        status_emoji = "✅" if result["status"] == "PASSED" else "❌"
        md.append(f"**状态**: {status_emoji} {result['status']}")
        md.append(f"**耗时**: {result.get('duration', 0):.2f}s\n")

        # 从stdout中提取关键数据
        if "stdout" in result and result["stdout"]:
            md.append("```")
            # 只提取包含关键指标的行
            for line in result["stdout"].split("\n"):
                if any(keyword in line for keyword in ["===", "mean=", "p95=", "QPS=", "Total:"]):
                    md.append(line.strip())
            md.append("```\n")

    # 性能趋势（如果有多个历史记录）
    md.append("## 📈 性能趋势\n")
    md.append("_提示：运行多次性能测试以生成趋势图_\n")

    # 建议
    md.append("## 💡 优化建议\n")
    suggestions = generate_suggestions(metrics)
    for suggestion in suggestions:
        md.append(f"- {suggestion}")
    md.append("")

    return "\n".join(md)


def extract_metrics_from_results(results: dict) -> dict:
    """从测试结果中提取结构化指标"""
    metrics = {}

    for test_name, result in results.items():
        if "stdout" not in result:
            continue

        stdout = result["stdout"]

        # 提取QA指标
        if "QA" in test_name or "qa" in test_name.lower():
            metrics["qa_e2e"] = {}
            for line in stdout.split("\n"):
                if "P95:" in line:
                    try:
                        val = float(line.split("P95:")[1].split("ms")[0].strip())
                        metrics["qa_e2e"]["p95_latency"] = val
                    except:
                        pass
                if "QPS:" in line or "QPS=" in line:
                    try:
                        val = float(line.split("QPS")[-1].split()[0].replace(":", "").replace("=", "").strip())
                        metrics["qa_e2e"]["qps"] = val
                    except:
                        pass

        # 提取Embedding指标
        if "Embedding" in test_name or "embedding" in test_name.lower():
            metrics["embedding"] = {}
            for line in stdout.split("\n"):
                if "p95=" in line:
                    try:
                        val = float(line.split("p95=")[1].split("ms")[0].strip())
                        metrics["embedding"]["p95_latency"] = val
                    except:
                        pass

        # 提取Vector Store指标
        if "Vector" in test_name or "vector" in test_name.lower():
            metrics["vector_store"] = {}
            for line in stdout.split("\n"):
                if "p95=" in line:
                    try:
                        val = float(line.split("p95=")[1].split("ms")[0].strip())
                        metrics["vector_store"]["query_latency"] = val
                    except:
                        pass

    return metrics


def generate_suggestions(metrics: dict) -> list[str]:
    """根据指标生成优化建议"""
    suggestions = []

    if "qa_e2e" in metrics:
        qa = metrics["qa_e2e"]
        if qa.get("p95_latency", 0) > 2000:
            suggestions.append("⚠️ QA P95延迟超过2秒，考虑优化：1) 使用更快的embedding模型 2) 添加结果缓存 3) 减少LLM生成token数")
        if qa.get("qps", 0) < 1:
            suggestions.append("⚠️ QPS低于1，考虑：1) 使用异步处理 2) 批量embedding 3) 连接池优化")

    if "embedding" in metrics:
        emb = metrics["embedding"]
        if emb.get("p95_latency", 0) > 100:
            suggestions.append("⚠️ Embedding延迟较高，考虑：1) 切换到本地模型 2) 使用GPU加速 3) 批量处理")

    if "vector_store" in metrics:
        vs = metrics["vector_store"]
        if vs.get("query_latency", 0) > 500:
            suggestions.append("⚠️ 向量查询较慢，考虑：1) 使用Milvus等分布式向量数据库 2) 优化索引参数 3) 减少返回结果数")

    if not suggestions:
        suggestions.append("✅ 所有指标正常，系统性能良好")

    return suggestions


def get_system_info() -> str:
    """获取系统信息"""
    import platform
    return f"{platform.system()} {platform.release()}"


def main():
    """生成最新的性能报告"""
    results_dir = Path("tests/performance/results")

    if not results_dir.exists() or not list(results_dir.glob("*.json")):
        print("❌ 未找到性能测试结果，请先运行: python tests/performance/run_benchmarks.py")
        return

    # 找到最新的测试结果
    latest = max(results_dir.glob("*.json"), key=lambda p: p.stat().st_mtime)

    print(f"📊 生成性能报告: {latest.name}")

    # 生成Markdown报告
    markdown = generate_markdown_report(latest)

    # 保存报告
    report_file = results_dir / f"report_{latest.stem.replace('benchmark_', '')}.md"
    with open(report_file, "w", encoding="utf-8") as f:
        f.write(markdown)

    print(f"✅ 报告已生成: {report_file}")
    print("\n预览:\n")
    print(markdown[:1000])
    print("\n...")


if __name__ == "__main__":
    main()
