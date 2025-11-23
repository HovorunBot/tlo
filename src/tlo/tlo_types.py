"""Collection of generic types and type aliases for TLO application."""

__all__ = ["FuncName", "TTaskDecorator", "TTaskFunc", "TaskId"]

from collections.abc import Awaitable, Callable
from typing import Any

type TTaskFunc = Callable[..., Any] | Callable[..., Awaitable[Any]]
type TTaskDecorator = Callable[[TTaskFunc], TTaskFunc]
type TaskId = str
type FuncName = str
