"""Minimal logging configuration."""
from __future__ import annotations

import logging
import sys


_CONFIGURED = False


def configure_logging(enabled: bool = True, level: int = logging.INFO) -> None:
    global _CONFIGURED
    if _CONFIGURED:
        return

    root = logging.getLogger()
    root.setLevel(level if enabled else logging.WARNING)

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(
        logging.Formatter(
            fmt="%(asctime)s %(levelname)s [%(name)s] %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
    )
    # Replace any existing handlers to avoid duplicates on re-runs.
    root.handlers = [handler]
    _CONFIGURED = True


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)