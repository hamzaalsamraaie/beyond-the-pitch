"""Structured logging for the entire pipeline."""

import logging
import sys
from datetime import datetime
from pathlib import Path

import structlog


def _get_log_path() -> Path:
    root = Path(__file__).resolve().parents[2]
    log_dir = root / "logs"
    log_dir.mkdir(exist_ok=True)
    stamp = datetime.now().strftime("%Y-%m-%d")
    return log_dir / f"pipeline_{stamp}.log"


def configure_logging(level: str = "INFO") -> None:
    """Call once at process start to wire up structlog → stdlib → file+stdout."""
    numeric = getattr(logging, level.upper(), logging.INFO)

    log_path = _get_log_path()
    file_handler = logging.FileHandler(log_path, encoding="utf-8")
    file_handler.setLevel(numeric)

    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setLevel(numeric)

    logging.basicConfig(
        level=numeric,
        handlers=[file_handler, stream_handler],
        format="%(message)s",
    )

    structlog.configure(
        processors=[
            structlog.stdlib.add_log_level,
            structlog.stdlib.add_logger_name,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.ExceptionRenderer(),
            structlog.dev.ConsoleRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(numeric),
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
    )


def get_logger(name: str) -> structlog.BoundLogger:
    return structlog.get_logger(name)
