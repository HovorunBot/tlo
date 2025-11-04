"""Collection of generic types and type aliases for TLO application."""

__all__ = ["FuncName", "TImplementation", "TStrEnum", "TTaskDecorator", "TTaskFunc", "TaskId"]

from collections.abc import Awaitable, Callable
from typing import Any, TypeAlias, TypeVar

from tlo.py_compatibility import StrEnum

TTaskFunc = Callable[..., Any] | Callable[..., Awaitable[Any]]
TTaskDecorator = Callable[[TTaskFunc], TTaskFunc]
TStrEnum = TypeVar("TStrEnum", bound=StrEnum)
TImplementation = TypeVar("TImplementation")
TaskId: TypeAlias = str
FuncName: TypeAlias = str
