"""Data structures describing background task registrations."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import timedelta
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from tlo.tlo_types import FuncName, TTaskFunc


@dataclass(slots=True)
class TaskDef:
    """Store metadata about a callable that was registered as a background task.

    :param func: Callable executed when the task is dispatched.
    :param name: Name under which the task is registered.
    :param extra: Arbitrary metadata provided at registration time.
    :param interval: Optional scheduling hint as ``datetime.timedelta`` or seconds,
        normalised to ``timedelta`` during initialisation.
    :param exclusive: Whether the task must be executed exclusively.
    """

    func: TTaskFunc
    name: FuncName
    extra: dict[str, Any] = field(default_factory=dict)
    interval: timedelta | int | None = None
    exclusive: bool = False

    def __post_init__(self) -> None:
        """Normalise interval values provided as integers to ``timedelta``."""
        if isinstance(self.interval, int):
            self.interval = timedelta(seconds=self.interval)
