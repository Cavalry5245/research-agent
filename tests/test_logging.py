import json
import logging

from app.logging_config import configure_logging, get_logger


def test_configure_logging_writes_json_log(tmp_path):
    log_path = tmp_path / "app.jsonl"
    configure_logging(str(log_path))
    logger = get_logger("tests.logging")

    logger.info("test_event", extra={"ra_request_id": "req_1", "ra_duration_ms": 12.5})

    line = log_path.read_text(encoding="utf-8").strip().splitlines()[-1]
    payload = json.loads(line)
    assert payload["event"] == "test_event"
    assert payload["level"] == "info"
    assert payload["logger"] == "tests.logging"
    assert payload["request_id"] == "req_1"
    assert payload["duration_ms"] == 12.5


def test_configure_logging_replaces_previous_research_agent_handler(tmp_path):
    first = tmp_path / "first.jsonl"
    second = tmp_path / "second.jsonl"

    configure_logging(str(first))
    configure_logging(str(second))

    handlers = [
        handler
        for handler in logging.getLogger().handlers
        if getattr(handler, "_research_agent_json_handler", False)
    ]
    assert len(handlers) == 1
