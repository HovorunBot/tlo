"""Registry utilities used to keep track of background task definitions."""

from __future__ import annotations

__all__ = ["DEFAULT_REGISTRY", "TaskRegistry", "register"]

from collections.abc import Awaitable, Callable
from datetime import timedelta
from typing import Any

from tlo.task_registry.task_def import TaskDef

TaskCallback = Callable[..., Any] | Callable[..., Awaitable[Any]]
TaskDecorator = Callable[[TaskCallback], TaskCallback]


class TaskRegistry:
    """Store and retrieve task definitions registered with the TLO runtime."""

    def __init__(self) -> None:
        """Initialise an empty registry of task definitions."""
        self._tasks: dict[str, TaskDef] = {}

    def register(
        self,
        name: str | None = None,
        *,
        interval: int | timedelta | None = None,
        extra: dict[str, Any] | None = None,
    ) -> TaskDecorator:
        """Register a callable as a background task.

        Parameters
        ----------
        name:
            Optional explicit name under which the task will be stored.
            When omitted the callable's ``__name__`` attribute is used.
        interval:
            An optional scheduling hint. Supplying an integer is treated as a
            number of seconds and converted to ``datetime.timedelta``.
        extra:
            Arbitrary metadata that will be preserved on the resulting
            :class:`~tlo.task_registry.task_def.TaskDef` instance.

        """

        def decorator(func: TaskCallback) -> TaskCallback:
            """Store the provided callable and return it unchanged."""
            task_name = name or func.__name__
            schedule = timedelta(seconds=interval) if isinstance(interval, int) else interval
            self._tasks[task_name] = TaskDef(
                name=task_name,
                func=func,
                interval=schedule,
                extra=extra or {},
            )
            return func

        return decorator

    def get_task(self, name: str) -> TaskDef:
        """Return the task definition registered under *name*."""
        return self._tasks[name]

    def list_tasks(self) -> list[TaskDef]:
        """Return all registered task definitions."""
        return list(self._tasks.values())

    def list_task_names(self) -> list[str]:
        """Return the names of all registered tasks."""
        return list(self._tasks.keys())

    def __getitem__(self, name: str) -> TaskDef:
        """Support dictionary-style access to registered task definitions."""
        return self._tasks[name]

    def __contains__(self, name: str) -> bool:
        """Return ``True`` when a task is registered under *name*."""
        return name in self._tasks


DEFAULT_REGISTRY = TaskRegistry()
register = DEFAULT_REGISTRY.register
