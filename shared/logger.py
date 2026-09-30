"""统一日志：JSON lines 格式（design.md §6.3）。

每行一条 JSON，便于日志分析工具解析。用法：

    from shared.logger import get_logger
    logger = get_logger(__name__)
    logger.info("message", extra={"extra_field": "value"})
"""

from __future__ import annotations

import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

_DEFAULT_FORMAT = "%Y-%m-%dT%H:%M:%S%z"


class JsonLineFormatter(logging.Formatter):
    """将 LogRecord 渲染为单行 JSON。"""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, object] = {
            "time": datetime.fromtimestamp(record.created, tz=timezone.utc)
            .astimezone()
            .strftime(_DEFAULT_FORMAT),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)

        # 标准属性之外、通过 extra= 传入的字段
        standard = set(logging.LogRecord("", 0, "", 0, "", None, None).__dict__) | {
            "message",
            "asctime",
        }
        for key, value in record.__dict__.items():
            if key not in standard and not key.startswith("_"):
                try:
                    json.dumps(value)
                except TypeError:
                    value = repr(value)
                payload[key] = value
        return json.dumps(payload, ensure_ascii=False)


def get_logger(name: str = "daily-report", log_file: str | Path | None = None) -> logging.Logger:
    """获取一个输出 JSON lines 的 logger；重复调用不会重复添加 handler。"""

    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)
    logger.propagate = False

    if not any(getattr(h, "_jsonline", False) for h in logger.handlers):
        stream_handler = logging.StreamHandler(stream=sys.stderr)
        stream_handler.setFormatter(JsonLineFormatter())
        stream_handler._jsonline = True  # type: ignore[attr-defined]
        logger.addHandler(stream_handler)

        if log_file is not None:
            path = Path(log_file)
            path.parent.mkdir(parents=True, exist_ok=True)
            file_handler = logging.FileHandler(path, encoding="utf-8")
            file_handler.setFormatter(JsonLineFormatter())
            file_handler._jsonline = True  # type: ignore[attr-defined]
            logger.addHandler(file_handler)

    return logger
