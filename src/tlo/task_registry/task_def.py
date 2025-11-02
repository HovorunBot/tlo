"""Data structures describing background task registrations."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import timedelta
from typing import Any

TaskCallback = Callable[..., Any] | Callable[..., Awaitable[Any]]


@dataclass(slots=True)
class TaskDef:
    """Store metadata about a callable that was registered as a background task.

    Parameters
    ----------
    func:
        The callable that will be executed when the task is dispatched.
    name:
        Name under which the task is registered.
    extra:
        Arbitrary metadata provided by the user at registration time.
    interval:
        Optional scheduling hint. The value can be specified either as a
        ``datetime.timedelta`` instance or as a number of seconds, and is
        normalised to ``timedelta`` during initialisation.

    """

    func: TaskCallback
    name: str
    extra: dict[str, Any] = field(default_factory=dict)
    interval: timedelta | int | None = None

    def __post_init__(self) -> None:
        """Normalise interval values provided as integers to ``timedelta``."""
        if isinstance(self.interval, int):
            self.interval = timedelta(seconds=self.interval)
