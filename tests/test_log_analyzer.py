import json

from app.analytics.log_analyzer import analyze_logs, generate_report, load_jsonl_logs


def test_analyze_logs_computes_endpoint_counts_and_latency():
    records = [
        {
            "event": "api_request",
            "path": "/health",
            "status_code": 200,
            "duration_ms": 10,
        },
        {
            "event": "api_request",
            "path": "/health",
            "status_code": 500,
            "duration_ms": 30,
        },
        {"event": "qa_completed", "paper_id": "paper_001"},
    ]

    analysis = analyze_logs(records)

    assert analysis["api_request_count"] == 2
    assert analysis["error_rate"] == 0.5
    assert analysis["endpoint_counts"] == {"/health": 2}
    assert analysis["endpoint_latency"]["/health"]["p50_ms"] == 20.0
    assert analysis["service_events"] == {"qa_completed": 1}


def test_generate_report_writes_markdown(tmp_path):
    log_file = tmp_path / "app.jsonl"
    output = tmp_path / "report.md"
    records = [
        {
            "event": "api_request",
            "path": "/tasks",
            "status_code": 200,
            "duration_ms": 5,
        },
        {"event": "note_generated", "paper_id": "paper_001"},
    ]
    log_file.write_text(
        "\n".join(json.dumps(record) for record in records), encoding="utf-8"
    )

    analysis = generate_report(log_file, output)

    assert analysis["total_records"] == 2
    report = output.read_text(encoding="utf-8")
    assert "# 日志分析报告" in report
    assert "`/tasks`: 1" in report
    assert "`note_generated`: 1" in report


def test_load_jsonl_logs_returns_empty_for_missing_file(tmp_path):
    assert load_jsonl_logs(tmp_path / "missing.jsonl") == []
