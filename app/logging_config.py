from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.fromtimestamp(
                record.created, timezone.utc
            ).isoformat(),
            "level": record.levelname.lower(),
            "event": record.getMessage(),
            "logger": record.name,
        }
        for key, value in record.__dict__.items():
            if key.startswith("ra_"):
                payload[key[3:]] = value
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False)


def configure_logging(log_path: str | None = None) -> str:
    resolved_path = log_path or os.getenv(
        "RESEARCH_AGENT_LOG_PATH", "app/storage/logs/app.jsonl"
    )
    Path(resolved_path).parent.mkdir(parents=True, exist_ok=True)

    handler = logging.FileHandler(resolved_path, encoding="utf-8")
    handler.setFormatter(JsonFormatter())

    root_logger = logging.getLogger()
    for existing in list(root_logger.handlers):
        if getattr(existing, "_research_agent_json_handler", False):
            root_logger.removeHandler(existing)
            existing.close()

    handler._research_agent_json_handler = True
    root_logger.addHandler(handler)
    root_logger.setLevel(logging.INFO)
    return resolved_path


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)
