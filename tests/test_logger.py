"""shared/logger.py 单元测试。"""

from __future__ import annotations

import json
import logging
from pathlib import Path

from shared.logger import JsonLineFormatter, get_logger


def test_jsonline_formatter_outputs_json() -> None:
    record = logging.LogRecord(
        name="test",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="hello %s",
        args=("world",),
        exc_info=None,
    )
    line = JsonLineFormatter().format(record)
    payload = json.loads(line)
    assert payload["level"] == "INFO"
    assert payload["message"] == "hello world"
    assert payload["logger"] == "test"
    assert "time" in payload


def test_get_logger_emits_jsonline(tmp_path: Path) -> None:
    log_file = tmp_path / "app.log"
    logger = get_logger("test-logger-file", log_file=log_file)
    logger.info("一条测试", extra={"pipeline": "collector"})

    lines = log_file.read_text(encoding="utf-8").strip().splitlines()
    payload = json.loads(lines[-1])
    assert payload["message"] == "一条测试"
    assert payload["pipeline"] == "collector"


def test_get_logger_does_not_duplicate_handlers() -> None:
    logger_a = get_logger("test-logger-unique")
    handler_count = len(logger_a.handlers)
    logger_b = get_logger("test-logger-unique")
    assert len(logger_b.handlers) == handler_count
