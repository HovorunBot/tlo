"""Registry utilities used to keep track of background task definitions."""

from __future__ import annotations

__all__ = [
    "KNOWN_TASK_REGISTRIES",
    "AbstractTaskRegistry",
    "InMemoryTaskRegistry",
    "TaskRegistryProtocol",
]

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any, Protocol, TypedDict, runtime_checkable

from tlo.common import TaskRegistryEnum
from tlo.errors import TaskIsNotRegisteredError
from tlo.task_registry.task_def import TaskDef
from tlo.utils import make_specific_register_func

if TYPE_CHECKING:
    from datetime import timedelta

    from tlo.py_compatibility import Unpack
    from tlo.tlo_types import TTaskDecorator, TTaskFunc


class _TaskDefKwargs(TypedDict):
    name: str
    func: TTaskFunc
    interval: timedelta | int | None
    extra: dict[str, Any]


KNOWN_TASK_REGISTRIES: dict[TaskRegistryEnum, type[TaskRegistryProtocol]] = {}

_register = make_specific_register_func(KNOWN_TASK_REGISTRIES)


@runtime_checkable
class TaskRegistryProtocol(Protocol):
    """Structural contract for task registry implementations.

    Concrete registries store metadata about callables scheduled as background tasks.
    """

    def register(
        self,
        name: str | None = None,
        *,
        interval: int | timedelta | None = None,
        extra: dict[str, Any] | None = None,
    ) -> TTaskDecorator:
        """Return a decorator that stores the wrapped callable in the registry.

        :param name: Optional explicit name used to register the task.
        :param interval: Optional scheduling hint expressed in seconds or as ``datetime.timedelta``.
        :param extra: Arbitrary metadata retained alongside the task definition.
        :returns: A decorator that registers the wrapped callable.
        """

    def get_task(self, name: str) -> TaskDef:
        """Return the task definition registered under *name*.

        :param name: Identifier previously supplied when the task was registered.
        """

    def list_tasks(self) -> list[TaskDef]:
        """Return the collection of registered task definitions."""

    def list_task_names(self) -> list[str]:
        """Return the names of all registered tasks."""

    def contains_task(self, name: str) -> bool:
        """Return ``True`` when a task is registered under *name*."""


class AbstractTaskRegistry(TaskRegistryProtocol, ABC):
    """Abstract base class for task registries.

    Specify public interfaces for any Registry implementation which may be used by TLO application
    """

    def register(
        self,
        name: str | None = None,
        *,
        interval: int | timedelta | None = None,
        extra: dict[str, Any] | None = None,
    ) -> TTaskDecorator:
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

        def decorator(func: TTaskFunc) -> TTaskFunc:
            """Store the provided callable and return it unchanged."""
            task_name = name or func.__name__
            self._register(name=task_name, func=func, interval=interval, extra=extra or {})
            return func

        return decorator

    @abstractmethod
    def get_task(self, name: str) -> TaskDef:
        """Return the task from the registry with the given name.

        :param name: The name of the task to retrieve.
        :raise TaskIsNotRegisteredError: If the task is not registered.
        """

    @abstractmethod
    def list_tasks(self) -> list[TaskDef]:
        """Return a list of all registered tasks."""

    @abstractmethod
    def list_task_names(self) -> list[str]:
        """Return a list of all registered task names."""

    @abstractmethod
    def contains_task(self, name: str) -> bool:
        """Return ``True`` if a task is registered under *name*."""

    @abstractmethod
    def _register(self, **task_def_kwargs: Unpack[_TaskDefKwargs]) -> None:
        """Register a task with the given name, function, interval, and extra metadata.

        It is a private implementation detail for the basic "@register" annotation.

        :param name: The name of the task to register.
        :type name: str
        :param func: The function to register as the task.
        :type func: TTaskFunc
        :param interval: The interval to schedule the task.
        :type interval: timedelta | int | None
        :param extra: Extra metadata to store with the task.
        :type extra: dict[str, Any]
        """


@_register(TaskRegistryEnum.InMemoryTaskRegistry)
class InMemoryTaskRegistry(AbstractTaskRegistry):
    """Store and retrieve task definitions registered with the TLO runtime."""

    def __init__(self) -> None:
        """Initialize an empty registry of task definitions."""
        self._tasks: dict[str, TaskDef] = {}

    def _register(self, **task_def_kwargs: Unpack[_TaskDefKwargs]) -> None:
        """Register a task with the given name, function, interval, and extra metadata."""
        self._tasks[task_def_kwargs["name"]] = TaskDef(**task_def_kwargs)

    def get_task(self, name: str) -> TaskDef:
        """Return the task definition registered under *name*."""
        if name not in self._tasks:
            msg = (
                f"Task {name!r} is not registered. Ensure you don't made a typo "
                f"or registred specified task into registry"
            )
            raise TaskIsNotRegisteredError(msg)
        return self._tasks[name]

    def list_tasks(self) -> list[TaskDef]:
        """Return all registered task definitions."""
        return list(self._tasks.values())

    def list_task_names(self) -> list[str]:
        """Return the names of all registered tasks."""
        return list(self._tasks.keys())

    def contains_task(self, name: str) -> bool:
        """Return ``True`` if a task is registered under *name*."""
        return name in self._tasks
