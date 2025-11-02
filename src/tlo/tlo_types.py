"""Collection of generic types and type aliases for TLO application."""

__all__ = ["TTaskDecorator", "TTaskFunc", "Unpack"]

from collections.abc import Awaitable, Callable
import sys
from typing import Any

if sys.version_info < (3, 11):
    from typing_extensions import Unpack
else:
    from typing import Unpack

TTaskFunc = Callable[..., Any] | Callable[..., Awaitable[Any]]
TTaskDecorator = Callable[[TTaskFunc], TTaskFunc]
