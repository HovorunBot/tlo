"""Tests for logging helpers and mixins."""

from __future__ import annotations

import logging

import pytest

from tlo.logging import DEFAULT_LOG_FORMAT, WithLogger, configure_logging


class ExampleLogger(WithLogger):
    """Concrete class for exercising the WithLogger mixin."""


def test_with_logger_caches_logger_named_after_class() -> None:
    """_logger should resolve to a class-named logger and cache the instance."""
    example = ExampleLogger()
    logger = example._logger  # noqa: SLF001
    assert logger.name == ExampleLogger.__name__
    assert logger is example._logger  # noqa: SLF001
    assert logger is ExampleLogger._get_logger()  # noqa: SLF001


def test_configure_logging_sets_root_level_and_formatter() -> None:
    """configure_logging should apply level and formatter to the root logger."""
    root_logger = logging.getLogger()
    original_handlers = list(root_logger.handlers)
    original_level = root_logger.level
    for handler in list(root_logger.handlers):
        root_logger.removeHandler(handler)

    try:
        configure_logging(level="DEBUG")
        assert root_logger.level == logging.DEBUG
        assert root_logger.handlers

        formatter = root_logger.handlers[0].formatter
        assert formatter is not None
        assert formatter._style._fmt == DEFAULT_LOG_FORMAT  # noqa: SLF001
    finally:
        for handler in list(root_logger.handlers):
            root_logger.removeHandler(handler)
        root_logger.setLevel(original_level)
        for handler in original_handlers:
            root_logger.addHandler(handler)


def test_configure_logging_rejects_unknown_level() -> None:
    """String log level names must be valid."""
    with pytest.raises(ValueError, match="valid logging level name"):
        configure_logging(level="NOTALEVEL")
