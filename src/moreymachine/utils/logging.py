"""Logging helpers for MoreyMachine."""

from __future__ import annotations

import logging

DEFAULT_LOG_FORMAT = "%(asctime)s %(levelname)s [%(name)s] %(message)s"
DEFAULT_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


def configure_logging(level: int | str = "INFO", *, force: bool = False) -> None:
    """Configure root logging with a concise project-friendly format."""
    logging.basicConfig(
        level=level,
        format=DEFAULT_LOG_FORMAT,
        datefmt=DEFAULT_DATE_FORMAT,
        force=force,
    )
    logging.getLogger("moreymachine").setLevel(level)


def get_logger(name: str | None = None) -> logging.Logger:
    """Return a logger under the MoreyMachine namespace."""
    logger_name = "moreymachine" if name is None else name
    return logging.getLogger(logger_name)
