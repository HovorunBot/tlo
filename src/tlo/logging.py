"""Centralised logging configuration and helpers for TLO."""

from __future__ import annotations

from functools import cached_property
import logging
from typing import Final

__all__ = ["DEFAULT_LOG_FORMAT", "DEFAULT_LOG_LEVEL", "WithLogger", "configure_logging"]

DEFAULT_LOG_LEVEL: Final[int] = logging.INFO
DEFAULT_LOG_FORMAT: Final[str] = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"


def configure_logging(level: int | str = DEFAULT_LOG_LEVEL, fmt: str = DEFAULT_LOG_FORMAT) -> None:
    """Configure root logging with TLO defaults."""
    resolved_level = _resolve_level(level)
    logging.basicConfig(level=resolved_level, format=fmt)


def _resolve_level(level: int | str) -> int:
    """Return a numeric logging level from either a string name or integer value."""
    if isinstance(level, str):
        level_name = level.upper()
        mapping = logging.getLevelNamesMapping()
        if level_name not in mapping:
            msg = f"{level!r} is not a valid logging level name."
            raise ValueError(msg)
        return mapping[level_name]
    return int(level)


class WithLogger:
    """Mixin that provides a cached logger named after the subclass."""

    @classmethod
    def _get_logger(cls) -> logging.Logger:
        """Return a :class:`logging.Logger` bound to the class name."""
        return logging.getLogger(cls.__name__)

    @cached_property
    def _logger(self) -> logging.Logger:
        """Cached logger instance for the current object."""
        return self._get_logger()
