"""Collection of generic types and type aliases for TLO application."""

__all__ = ["TTaskFunc"]

from collections.abc import Awaitable, Callable
from typing import Any

TTaskFunc = Callable[..., Any] | Callable[..., Awaitable[Any]]
