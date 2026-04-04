"""Logging setup for doc2md."""

from __future__ import annotations

import logging
import logging.handlers
from pathlib import Path


def setup_logging(level: str = "INFO", log_file: str | None = None) -> None:
    """Configure root logger with console + optional rotating file handler."""
    numeric_level = getattr(logging, level.upper(), logging.INFO)
    fmt = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    datefmt = "%Y-%m-%d %H:%M:%S"

    handlers: list[logging.Handler] = [logging.StreamHandler()]

    if log_file:
        file_path = Path(log_file).expanduser()
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.handlers.RotatingFileHandler(
            file_path,
            maxBytes=5 * 1024 * 1024,  # 5MB
            backupCount=3,
            encoding="utf-8",
        )
        file_handler.setFormatter(logging.Formatter(fmt, datefmt))
        handlers.append(file_handler)

    logging.basicConfig(level=numeric_level, format=fmt, datefmt=datefmt, handlers=handlers)
