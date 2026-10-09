"""结构化日志配置。

- 控制台输出 JSON 结构化日志，便于采集；
- 应用日志按天切割，保留 30 天；
- 错误日志单独落文件。
"""

import json
import logging
import logging.handlers
import os
import sys
from datetime import datetime, timezone
from typing import Any, Dict

from app.core.config import settings

_CONFIGURED = False


class JsonFormatter(logging.Formatter):
    """把日志记录渲染成单行 JSON。"""

    def format(self, record: logging.LogRecord) -> str:
        payload: Dict[str, Any] = {
            "ts": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        # 合并通过 extra= 注入的自定义字段
        for key, value in record.__dict__.items():
            if key in {
                "name", "msg", "args", "levelname", "levelno", "pathname",
                "filename", "module", "exc_info", "exc_text", "stack_info",
                "lineno", "funcName", "created", "msecs", "relativeCreated",
                "thread", "threadName", "processName", "process", "taskName",
                "message",
            }:
                continue
            payload[key] = value
        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False)


def _build_file_handlers(log_dir: str, level: int):
    os.makedirs(log_dir, exist_ok=True)
    formatter = JsonFormatter()

    app_handler = logging.handlers.TimedRotatingFileHandler(
        os.path.join(log_dir, "app.log"),
        when="midnight",
        backupCount=30,
        encoding="utf-8",
    )
    app_handler.setLevel(level)
    app_handler.setFormatter(formatter)

    error_handler = logging.handlers.TimedRotatingFileHandler(
        os.path.join(log_dir, "error.log"),
        when="midnight",
        backupCount=30,
        encoding="utf-8",
    )
    error_handler.setLevel(logging.ERROR)
    error_handler.setFormatter(formatter)

    return app_handler, error_handler


def setup_logging() -> None:
    """初始化根 logger，重复调用幂等。"""
    global _CONFIGURED
    if _CONFIGURED:
        return

    level = getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO)
    root = logging.getLogger()
    root.setLevel(level)
    root.handlers.clear()

    console = logging.StreamHandler(sys.stdout)
    console.setLevel(level)
    console.setFormatter(JsonFormatter())
    root.addHandler(console)

    app_handler, error_handler = _build_file_handlers(settings.LOG_DIR, level)
    root.addHandler(app_handler)
    root.addHandler(error_handler)

    # 降低第三方库噪音
    for noisy in ("uvicorn.access", "httpx", "apscheduler"):
        logging.getLogger(noisy).setLevel(logging.WARNING)

    _CONFIGURED = True


def get_logger(name: str = "app") -> logging.Logger:
    setup_logging()
    return logging.getLogger(name)
