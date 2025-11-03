"""Define interfaces and in-memory helpers for persisting task state."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Protocol, runtime_checkable

from tlo.common import TaskStateStoreEnum
from tlo.utils import make_specific_register_func

if TYPE_CHECKING:
    from tlo.task_state_store.common import TaskStateRecord

KNOWN_TASK_STATE_STORES: dict[TaskStateStoreEnum, type[TaskStateStoreProtocol]] = {}


_register = make_specific_register_func(KNOWN_TASK_STATE_STORES)


@runtime_checkable
class TaskStateStoreProtocol(Protocol):
    """Protocol for task state stores."""

    def create(self, record: TaskStateRecord) -> None:
        """Persist a newly produced task state record.

        :param record: The serialisable state to store.
        """

    def update(self, record: TaskStateRecord) -> None:
        """Replace an existing task state record.

        :param record: State with the same identifier as the record to be updated.
        """

    def get(self, id_: str) -> TaskStateRecord | None:
        """Retrieve a stored record by identifier.

        :param id_: Unique identifier generated for the task state.
        :returns: The matching record or ``None`` when it is not present.
        """

    def delete(self, id_: str) -> None:
        """Remove a stored record.

        :param id_: Unique identifier of the record to delete.
        """


class AbstractTaskStateStore(TaskStateStoreProtocol, ABC):
    """Abstract base class for task state stores."""

    @abstractmethod
    def create(self, record: TaskStateRecord) -> None:
        """Create a new record in the task state store."""

    @abstractmethod
    def update(self, record: TaskStateRecord) -> None:
        """Update an existing record in the task state store."""

    @abstractmethod
    def get(self, id_: str) -> TaskStateRecord | None:
        """Retrieve a record from the task state store by its ID."""

    @abstractmethod
    def delete(self, id_: str) -> None:
        """Delete a record from the task state store by its ID."""


@_register(TaskStateStoreEnum.InMemoryTaskStateStore)
class InMemoryTaskStateStore(AbstractTaskStateStore):
    """In-memory implementation of the task state store."""

    def __init__(self) -> None:
        """Initialize an empty task state store dictionary."""
        self._store: dict[str, TaskStateRecord] = {}

    def create(self, record: TaskStateRecord) -> None:
        """Create a new record in the task state store."""
        self._store[record.id] = record

    def update(self, record: TaskStateRecord) -> None:
        """Update an existing record in the task state store."""
        self._store[record.id] = record

    def get(self, id_: str) -> TaskStateRecord | None:
        """Retrieve a record from the task state store by its ID."""
        return self._store.get(id_)

    def delete(self, id_: str) -> None:
        """Delete a record from the task state store by its ID."""
        del self._store[id_]
