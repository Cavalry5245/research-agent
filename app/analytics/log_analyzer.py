from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path
from statistics import median
from typing import Any


def _percentile(values: list[float], percentile: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = min(len(ordered) - 1, int(round((len(ordered) - 1) * percentile)))
    return ordered[index]


def load_jsonl_logs(log_file: str | Path) -> list[dict[str, Any]]:
    path = Path(log_file)
    if not path.exists():
        return []
    records = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        records.append(json.loads(line))
    return records


def analyze_logs(records: list[dict[str, Any]]) -> dict[str, Any]:
    api_records = [record for record in records if record.get("event") == "api_request"]
    endpoint_counts = Counter(record.get("path", "unknown") for record in api_records)
    status_counts = Counter(str(record.get("status_code", "unknown")) for record in api_records)
    durations_by_path: dict[str, list[float]] = defaultdict(list)
    for record in api_records:
        durations_by_path[record.get("path", "unknown")].append(float(record.get("duration_ms", 0.0)))

    endpoint_latency = {}
    for path, durations in durations_by_path.items():
        endpoint_latency[path] = {
            "count": len(durations),
            "p50_ms": median(durations),
            "p95_ms": _percentile(durations, 0.95),
        }

    service_events = Counter(
        record.get("event", "unknown")
        for record in records
        if record.get("event") != "api_request"
    )

    error_count = sum(
        1
        for record in api_records
        if int(record.get("status_code", 0) or 0) >= 400
    )
    error_rate = error_count / len(api_records) if api_records else 0.0

    return {
        "total_records": len(records),
        "api_request_count": len(api_records),
        "error_rate": error_rate,
        "endpoint_counts": dict(endpoint_counts),
        "status_counts": dict(status_counts),
        "endpoint_latency": endpoint_latency,
        "service_events": dict(service_events),
    }


def render_markdown_report(analysis: dict[str, Any]) -> str:
    lines = [
        "# 日志分析报告",
        "",
        f"- 总日志数：{analysis['total_records']}",
        f"- API 请求数：{analysis['api_request_count']}",
        f"- API 错误率：{analysis['error_rate']:.2%}",
        "",
        "## 接口调用次数",
    ]
    for path, count in sorted(analysis["endpoint_counts"].items()):
        lines.append(f"- `{path}`: {count}")

    lines.extend(["", "## 接口延迟"])
    for path, stats in sorted(analysis["endpoint_latency"].items()):
        lines.append(
            f"- `{path}`: count={stats['count']}, p50={stats['p50_ms']:.2f}ms, p95={stats['p95_ms']:.2f}ms"
        )

    lines.extend(["", "## 服务事件"])
    for event, count in sorted(analysis["service_events"].items()):
        lines.append(f"- `{event}`: {count}")
    return "\n".join(lines) + "\n"


def generate_report(log_file: str | Path, output: str | Path) -> dict[str, Any]:
    records = load_jsonl_logs(log_file)
    analysis = analyze_logs(records)
    report = render_markdown_report(analysis)
    output_path = Path(output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(report, encoding="utf-8")
    return analysis


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--log-file", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    generate_report(args.log_file, args.output)


if __name__ == "__main__":
    main()
