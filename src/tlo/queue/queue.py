"""Queue strategies and helper building blocks used by the TLO runtime."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections import defaultdict, deque
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Protocol, runtime_checkable

from tlo.common import QueueEnum
from tlo.errors import TloQueueEmptyError
from tlo.logging import WithLogger
from tlo.utils import make_specific_register_func

if TYPE_CHECKING:
    from tlo.queue.queued_item import QueuedTask
    from tlo.settings import TloSettings
    from tlo.tlo_types import TaskId


def _queue_sort_key(qt: QueuedTask) -> datetime:
    """Sort by ETA when provided, otherwise by enqueue timestamp."""
    if qt.eta is None:
        return qt.enqueued_at

    assert isinstance(qt.eta, datetime), "Must be datetime for ETA at this point"
    return qt.eta


KNOWN_QUEUES: dict[QueueEnum, type[QueueProtocol]] = {}
_register = make_specific_register_func(KNOWN_QUEUES)


@runtime_checkable
class QueueProtocol(Protocol):
    """Public interface for queue implementations."""

    settings: TloSettings

    @property
    def default_queue(self) -> str:
        """Return the default queue name."""

    def enqueue(self, item: QueuedTask) -> None:
        """Add a task to the queue to be executed later."""

    def dequeue(self, queue_name: str | None = None) -> QueuedTask:
        """Return the next eligible task, honouring ETA and exclusiveness.

        :param queue_name: Optional queue name to dequeue from.
            If not provided, a default queue is used.
        :return: The next eligible task.
        :raises TloQueueEmptyError: If the queue is empty.
        """

    def dequeue_any_unsafe(self, queue_name: str | None = None) -> QueuedTask:
        """Return the next task ignoring ETA checks (unsafe, for admin flows only)."""

    def peek(self, queue_name: str | None = None) -> QueuedTask | None:
        """Non-destructive look at next eligible task."""

    def remove(self, task_id: TaskId) -> None:
        """Remove a task from the queue without actually executing it."""

    def reschedule(self, task_id: TaskId, *, eta: datetime | float | None) -> None:
        """Update the ETA for a queued task."""

    def move(self, task_id: TaskId, *, queue_name: str) -> None:
        """Move a task to a different queue."""

    def bulk_peek(self, queue_name: str | None = None, *, limit: int | None = None) -> list[QueuedTask]:
        """Return up to *limit* eligible tasks without removing them."""

    def __len__(self) -> int:
        """Return the number of tasks in any provided queue."""

    def total_tasks_by_queue(self) -> dict[str, int]:
        """Return a dictionary of tasks grouped by queue name."""

    def total_tasks(self) -> int:
        """Return a number of tasks in all queues."""


class AbstractQueue(WithLogger, QueueProtocol, ABC):
    """Base helper providing common logic and validation."""

    def __init__(self, settings: TloSettings) -> None:
        """Store configuration used by queue implementations."""
        self._settings = settings

    @property
    def default_queue(self) -> str:
        """Return the default queue name."""
        return self._settings.default_queue

    @abstractmethod
    def enqueue(self, item: QueuedTask) -> None:
        """Add a task to the queue to be executed later."""

    @abstractmethod
    def dequeue(self, queue_name: str | None = None) -> QueuedTask:
        """Return the next eligible task, honouring ETA and exclusiveness."""

    @abstractmethod
    def dequeue_any_unsafe(self, queue_name: str | None = None) -> QueuedTask:
        """Return the next task ignoring ETA checks (unsafe, for admin flows only)."""

    @abstractmethod
    def peek(self, queue_name: str | None = None) -> QueuedTask | None:
        """Non-destructive look at next eligible task."""

    @abstractmethod
    def remove(self, task_id: TaskId) -> None:
        """Remove a task from the queue without actually executing it."""

    @abstractmethod
    def reschedule(self, task_id: TaskId, *, eta: datetime | float | None) -> None:
        """Update the ETA for a queued task."""

    @abstractmethod
    def move(self, task_id: TaskId, *, queue_name: str) -> None:
        """Move a task to a different queue."""

    @abstractmethod
    def bulk_peek(self, queue_name: str | None = None, *, limit: int | None = None) -> list[QueuedTask]:
        """Return up to *limit* eligible tasks without removing them."""

    @abstractmethod
    def __len__(self) -> int:
        """Return the number of tasks in any provided queue."""

    @abstractmethod
    def total_tasks_by_queue(self) -> dict[str, int]:
        """Return a dictionary of tasks grouped by queue name."""

    @abstractmethod
    def total_tasks(self) -> int:
        """Return a number of tasks in all queues."""


@_register(QueueEnum.SimpleInMemoryQueue)
class SimpleInMemoryQueue(AbstractQueue):
    """The simplest in-memory queue implementation represented as a linear queue.

    Filtration is made exclusively by iteration via the single queue record
    """

    def __init__(self, settings: TloSettings) -> None:
        """Initialize a queue as an empty list."""
        super().__init__(settings)
        self._queue: list[QueuedTask] = []

    def enqueue(self, item: QueuedTask) -> None:
        """Add a task to the queue and maintain ordering by ETA/enqueued time."""
        self._queue.append(item)
        self._queue.sort(key=_queue_sort_key)
        self._logger.debug("Enqueued task %s into queue %s", item.id, item.queue_name)

    def dequeue(self, queue_name: str | None = None) -> QueuedTask:
        """Return the next eligible task, honouring ETA and exclusiveness."""
        queue_name = queue_name or self._settings.default_queue

        if (qt := self._next_task(queue_name)) is not None:
            self._queue.remove(qt)
            self._logger.debug("Dequeued task %s from queue %s", qt.id, queue_name)
            return qt

        msg = f"No task found in {queue_name!r} queue."
        raise TloQueueEmptyError(msg)

    def peek(self, queue_name: str | None = None) -> QueuedTask | None:
        """Non-destructive look at next eligible task."""
        queue_name = queue_name or self._settings.default_queue
        return self._next_task(queue_name)

    def dequeue_any_unsafe(self, queue_name: str | None = None) -> QueuedTask:
        """Remove next task for queue without ETA checks (unsafe)."""
        queue_name = queue_name or self._settings.default_queue
        for idx, qt in enumerate(self._queue):
            if qt.queue_name == queue_name:
                self._logger.debug("Dequeued task %s unsafely from queue %s", qt.id, queue_name)
                return self._queue.pop(idx)

        msg = f"No task found in {queue_name!r} queue."
        raise TloQueueEmptyError(msg)

    def _next_task(self, queue_name: str | None) -> QueuedTask | None:
        """Return the next eligible task for the given queue name, if any."""
        queue_name = queue_name or self._settings.default_queue

        queued_tasks = (qt for qt in self._queue if qt.queue_name == queue_name)
        now = datetime.now(UTC)
        for qt in queued_tasks:
            if qt.eta is None:
                return qt

            assert isinstance(qt.eta, datetime), "Must be datetime for ETA at this point"
            if qt.eta > now:
                continue

            return qt

        return None

    def remove(self, task_id: TaskId) -> None:
        """Remove a queued task from the queue by its ID.

        :raises TloQueueEmptyError: If the task is not found.
        """
        for idx, qt in enumerate(self._queue):
            if qt.id == task_id:
                del self._queue[idx]
                self._logger.debug("Removed task %s from queue %s", task_id, qt.queue_name)
                return
        msg = f"No task found for id {task_id!r}"
        raise TloQueueEmptyError(msg)

    def reschedule(self, task_id: TaskId, *, eta: datetime | float | None) -> None:
        """Update ETA for a queued task and maintain ordering."""
        for qt in self._queue:
            if qt.id != task_id:
                continue
            qt.eta = datetime.fromtimestamp(eta, UTC) if isinstance(eta, (int, float)) else eta
            self._queue.sort(key=_queue_sort_key)
            self._logger.debug("Rescheduled task %s in queue %s", task_id, qt.queue_name)
            return
        msg = f"No task found for id {task_id!r}"
        raise TloQueueEmptyError(msg)

    def move(self, task_id: TaskId, *, queue_name: str) -> None:
        """Move a queued task to another queue and reorder."""
        for qt in self._queue:
            if qt.id != task_id:
                continue
            qt.queue_name = queue_name
            self._queue.sort(key=_queue_sort_key)
            self._logger.debug("Moved task %s to queue %s", task_id, queue_name)
            return
        msg = f"No task found for id {task_id!r}"
        raise TloQueueEmptyError(msg)

    def bulk_peek(self, queue_name: str | None = None, *, limit: int | None = None) -> list[QueuedTask]:
        """Return up to *limit* eligible tasks without removing them."""
        queue_name = queue_name or self._settings.default_queue
        now = datetime.now(UTC)
        eligible: list[QueuedTask] = []
        for qt in (qt for qt in self._queue if qt.queue_name == queue_name):
            if qt.eta is not None and qt.eta > now:  # type: ignore[operator]
                continue
            eligible.append(qt)
            if limit is not None and len(eligible) >= limit:
                break
        return eligible

    def __len__(self) -> int:
        """Return the number of tasks in any provided queue."""
        return len(self._queue)

    def total_tasks_by_queue(self) -> dict[str, int]:
        """Return the number of tasks in each queue."""
        result: defaultdict[str, int] = defaultdict(int)
        for qt in self._queue:
            result[qt.queue_name] += 1
        return result

    def total_tasks(self) -> int:
        """Return the total number of tasks in all queues."""
        return len(self._queue)


@_register(QueueEnum.MapQueue)
class MapQueue(AbstractQueue):
    """Simplest queue implementation using :class:`collections.deque`.

    Designed for synchronous single-process operation.
    """

    def __init__(self, settings: TloSettings) -> None:
        """Initialize an empty in-memory queue based on map of `deque` objects.

        It is a bit more complicated than :class:`SimpleInMemoryQueue` but
        should avoid multiple unnecessary iterations and filtration compared to `SimpleInMemoryQueue`.
        """
        super().__init__(settings)
        self._queue: defaultdict[str, deque[QueuedTask]] = defaultdict(lambda: deque())

    def enqueue(self, item: QueuedTask) -> None:
        """Add a task to the queue to be executed later."""
        queue = self._queue[item.queue_name]
        queue.append(item)
        # Re-sort to keep earliest ETA/enqueued tasks in front.
        sorted_queue = sorted(queue, key=_queue_sort_key)
        self._queue[item.queue_name] = deque(sorted_queue)
        self._logger.debug("Enqueued task %s into queue %s", item.id, item.queue_name)

    def dequeue(self, queue_name: str | None = None) -> QueuedTask:
        """Return and remove the next eligible task for the requested queue."""
        queue_name = queue_name or self._settings.default_queue
        queue = self._queue[queue_name]
        now = datetime.now(UTC)
        for _ in range(len(queue)):
            qt = queue[0]
            if qt.eta is None or qt.eta <= now:  # type: ignore[operator]
                self._logger.debug("Dequeued task %s from queue %s", qt.id, queue_name)
                return queue.popleft()
            queue.rotate(-1)
        msg = f"No task found in {queue_name!r} queue."
        raise TloQueueEmptyError(msg)

    def peek(self, queue_name: str | None = None) -> QueuedTask | None:
        """Return the next eligible task without removing it from the queue."""
        queue_name = queue_name or self._settings.default_queue

        queue = self._queue[queue_name]
        now = datetime.now(UTC)
        for _ in range(len(queue)):
            qt = queue[0]
            if qt.eta is None or qt.eta <= now:  # type: ignore[operator]
                return qt
            queue.rotate(-1)
        return None

    def dequeue_any_unsafe(self, queue_name: str | None = None) -> QueuedTask:
        """Remove and return next task ignoring ETA (unsafe, for admin flows only)."""
        queue_name = queue_name or self._settings.default_queue
        queue = self._queue[queue_name]
        try:
            self._logger.debug("Dequeuing task unsafely from queue %s", queue_name)
            return queue.popleft()
        except IndexError as exc:
            msg = f"No task found in {queue_name!r} queue."
            raise TloQueueEmptyError(msg) from exc

    def remove(self, task_id: TaskId) -> None:
        """Remove a queued task from the queue whenever it is.

        :raises TloQueueEmptyError: If the task is not found.
        """
        for queue in self._queue.values():
            for qt in queue:
                if qt.id != task_id:
                    continue
                queue.remove(qt)
                self._logger.debug("Removed task %s from queue %s", task_id, qt.queue_name)
                return
        msg = f"No task found for id {task_id!r}"
        raise TloQueueEmptyError(msg)

    def reschedule(self, task_id: TaskId, *, eta: datetime | float | None) -> None:
        """Update the ETA for a queued task and reorder within its queue."""
        for queue_name, queue in self._queue.items():
            for qt in queue:
                if qt.id != task_id:
                    continue
                qt.eta = datetime.fromtimestamp(eta, UTC) if isinstance(eta, (int, float)) else eta
                sorted_queue = sorted(queue, key=_queue_sort_key)
                self._queue[queue_name] = deque(sorted_queue)
                self._logger.debug("Rescheduled task %s in queue %s", task_id, queue_name)
                return
        msg = f"No task found for id {task_id!r}"
        raise TloQueueEmptyError(msg)

    def move(self, task_id: TaskId, *, queue_name: str) -> None:
        """Move a queued task to another queue and maintain ordering."""
        for source_queue, queue in list(self._queue.items()):
            for qt in list(queue):
                if qt.id != task_id:
                    continue
                queue.remove(qt)
                qt.queue_name = queue_name
                self.enqueue(qt)
                if not queue:
                    del self._queue[source_queue]
                self._logger.debug("Moved task %s from %s to queue %s", task_id, source_queue, queue_name)
                return
        msg = f"No task found for id {task_id!r}"
        raise TloQueueEmptyError(msg)

    def bulk_peek(self, queue_name: str | None = None, *, limit: int | None = None) -> list[QueuedTask]:
        """Return up to *limit* eligible tasks without removing them."""
        queue_name = queue_name or self._settings.default_queue
        queue = self._queue[queue_name]
        now = datetime.now(UTC)
        eligible: list[QueuedTask] = []
        for qt in queue:
            if qt.eta is not None and qt.eta > now:  # type: ignore[operator]
                continue
            eligible.append(qt)
            if limit is not None and len(eligible) >= limit:
                break
        return eligible

    def __len__(self) -> int:
        """Return a number of tasks stored across all map entries."""
        return sum(len(queue) for queue in self._queue.values())

    def total_tasks_by_queue(self) -> dict[str, int]:
        """Return counts of queued tasks per queue name."""
        return {queue_name: len(queue) for queue_name, queue in self._queue.items()}

    def total_tasks(self) -> int:
        """Return total number of tasks held by the map queue."""
        return len(self)
