"""Module specifiing queuing strategies."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections import defaultdict, deque
from datetime import datetime, timezone
import json
from typing import TYPE_CHECKING, Protocol, runtime_checkable

from typing_extensions import assert_never

from tlo.common import TLO_DEFAULT_QUEUE_NAME, QueueEnum, WithSqliteInMemory
from tlo.errors import NoTaskInQueueError
from tlo.queue.queued_item import QueuedTask
from tlo.utils import make_specific_register_func

if TYPE_CHECKING:
    from collections.abc import MutableSequence

    from tlo.tlo_types import TaskId

KNOWN_QUEUES: dict[QueueEnum, type[QueueProtocol]] = {}
_register = make_specific_register_func(KNOWN_QUEUES)


@runtime_checkable
class QueueProtocol(Protocol):
    """Public interface for queue implementations."""

    def enqueue(self, item: QueuedTask) -> None:
        """Add a task to the queue to be executed later."""

    def dequeue(self, queue_name: str = TLO_DEFAULT_QUEUE_NAME) -> QueuedTask:
        """Return the next eligible task, honouring ETA and exclusiveness.

        :param queue_name: Optional queue name to dequeue from.
            If not provided, a default queue is used.
        :return: The next eligible task.
        :raises EmptyQueueError: If the queue is empty.
        """

    def peek(self, queue_name: str = TLO_DEFAULT_QUEUE_NAME) -> QueuedTask | None:
        """Non-destructive look at next eligible task."""

    def remove(self, task_id: TaskId) -> None:
        """Remove a task from the queue without actually executing it."""

    def __len__(self) -> int:
        """Return the number of tasks in any provided queue."""

    def total_tasks_by_queue(self) -> dict[str, int]:
        """Return a dictionary of tasks grouped by queue name."""

    def total_tasks(self) -> int:
        """Return a number of tasks in all queues."""


class AbstractQueue(QueueProtocol, ABC):
    """Base helper providing common logic and validation."""

    @abstractmethod
    def enqueue(self, item: QueuedTask) -> None:
        """Add a task to the queue to be executed later."""

    @abstractmethod
    def dequeue(self, queue_name: str = TLO_DEFAULT_QUEUE_NAME) -> QueuedTask:
        """Return the next eligible task, honouring ETA and exclusiveness."""

    @abstractmethod
    def peek(self, queue_name: str = TLO_DEFAULT_QUEUE_NAME) -> QueuedTask | None:
        """Non-destructive look at next eligible task."""

    @abstractmethod
    def remove(self, task_id: TaskId) -> None:
        """Remove a task from the queue without actually executing it."""

    @abstractmethod
    def __len__(self) -> int:
        """Return the number of tasks in any provided queue."""

    @abstractmethod
    def total_tasks_by_queue(self) -> dict[str, int]:
        """Return a dictionary of tasks grouped by queue name."""

    @abstractmethod
    def total_tasks(self) -> int:
        """Return a number of tasks in all queues."""


class InsertQtMixin:
    """Mixin providing logic of inserting QueuedTask into the existing queue."""

    def _enqueue_without_eta(self, task: QueuedTask, queue: MutableSequence[QueuedTask]) -> None:
        assert task.eta is None, (
            "Incorrect call: function is exclusive for QueuedTask without provided ETA"
        )
        for idx, existing in enumerate(queue):
            if existing.eta is None:
                continue
            queue.insert(idx, task)
            return

        queue.append(task)

    def _enqueue_with_eta(self, task: QueuedTask, queue: MutableSequence[QueuedTask]) -> None:
        assert task.eta is not None, (
            "Incorrect call: function is exclusive for QueuedTask with provided ETA"
        )
        assert isinstance(task.eta, datetime), "Must be datetime for ETA at this point"
        for idx, existing in enumerate(queue):
            if existing.eta is None:
                continue
            assert isinstance(existing.eta, datetime), "Must be datetime for ETA at this point"
            if existing.eta <= task.eta:
                continue
            queue.insert(idx, task)
            return

        # If none of the items met the criteria, append to the right
        queue.append(task)


@_register(QueueEnum.SimpleInMemoryQueue)
class SimpleInMemoryQueue(AbstractQueue, InsertQtMixin):
    """The simplest in-memory queue implementation represented as a linear queue.

    Filtration is made exclusively by iteration via the single queue record
    """

    def __init__(self) -> None:
        """Initialize a queue as an empty list."""
        self._queue: list[QueuedTask] = []

    def enqueue(self, qt: QueuedTask) -> None:
        """Add a task to the queue to be executed later, respecting ETA order."""
        # If queue empty — append trivially
        match qt:
            case _ if not self._queue:
                self._queue.append(qt)
            case _ if qt.eta is None:
                self._enqueue_without_eta(qt, self._queue)
            case _ if qt.eta is not None:
                self._enqueue_with_eta(qt, self._queue)
            case _:
                assert_never(qt)

    def dequeue(self, queue_name: str = TLO_DEFAULT_QUEUE_NAME) -> QueuedTask:
        """Return the next eligible task, honouring ETA and exclusiveness."""
        if (qt := self._next_task(queue_name)) is not None:
            self._queue.remove(qt)
            return qt

        msg = f"No task found in {queue_name!r} queue."
        raise NoTaskInQueueError(msg)

    def peek(self, queue_name: str = TLO_DEFAULT_QUEUE_NAME) -> QueuedTask | None:
        """Non-destructive look at next eligible task."""
        return self._next_task(queue_name)

    def _next_task(self, queue_name: str = TLO_DEFAULT_QUEUE_NAME) -> QueuedTask | None:
        queued_tasks = (qt for qt in self._queue if qt.queue_name == queue_name)
        now = datetime.now(timezone.utc)
        for qt in queued_tasks:
            if qt.eta is None:
                return qt

            assert isinstance(qt.eta, datetime), "Must be datetime for ETA at this point"
            if qt.eta > now:
                break

            return qt

        return None

    def remove(self, task_id: TaskId) -> None:
        """Remove a queued task from the queue by its ID."""
        for idx, qt in enumerate(self._queue):
            if qt.id == task_id:
                del self._queue[idx]
                return

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
class MapQueue(AbstractQueue, InsertQtMixin):
    """Simplest queue implementation using :class:`collections.deque`.

    Designed for synchronous single-process operation.
    """

    def __init__(self) -> None:
        """Initialize an empty in-memory queue based on map of `deque` objects.

        It is a bit more complicated than :class:`SimpleInMemoryQueue` but
        should avoid multiple unnecessary iterations and filtration compared to `SimpleInMemoryQueue`.
        """
        self._queue: defaultdict[str, deque[QueuedTask]] = defaultdict(lambda: deque())

    def enqueue(self, qt: QueuedTask) -> None:
        """Add a task to the queue to be executed later."""
        queue = self._queue[qt.queue_name]
        match qt:
            case _ if not queue:
                queue.append(qt)
            case _ if qt.eta is None:
                self._enqueue_without_eta(qt, queue)
            case _ if qt.eta is not None:
                self._enqueue_with_eta(qt, queue)
            case _:
                assert_never(qt)

    def dequeue(self, queue_name: str = TLO_DEFAULT_QUEUE_NAME) -> QueuedTask:
        """Return and remove the next eligible task for the requested queue."""
        queue = self._queue[queue_name]
        now = datetime.now(timezone.utc)
        if queue and (queue[0].eta is None or queue[0].eta <= now):  # type: ignore[operator]
            return queue.popleft()
        msg = f"No task found in {queue_name!r} queue."
        raise NoTaskInQueueError(msg)

    def peek(self, queue_name: str = TLO_DEFAULT_QUEUE_NAME) -> QueuedTask | None:
        """Return the next eligible task without removing it from the queue."""
        queue = self._queue[queue_name]
        now = datetime.now(timezone.utc)
        if queue and (queue[0].eta is None or queue[0].eta <= now):  # type: ignore[operator]
            return queue[0]
        return None

    def remove(self, task_id: TaskId) -> None:
        """Remove a queued task from the queue whenever it is."""
        for queue in self._queue.values():
            for qt in queue:
                if qt.id != task_id:
                    continue
                queue.remove(qt)
                return

    def __len__(self) -> int:
        """Return a number of tasks stored across all map entries."""
        return sum(len(queue) for queue in self._queue.values())

    def total_tasks_by_queue(self) -> dict[str, int]:
        """Return counts of queued tasks per queue name."""
        return {queue_name: len(queue) for queue_name, queue in self._queue.items()}

    def total_tasks(self) -> int:
        """Return total number of tasks held by the map queue."""
        return len(self)


@_register(QueueEnum.InMemorySqliteQueue)
class InMemorySqliteQueue(AbstractQueue, WithSqliteInMemory):
    """Simplest queue implementation using in memory sqlite database."""

    def _init_schema(self) -> None:
        self.sqlite_connection.execute(QueuedTask.to_sql_table())
        self.sqlite_connection.commit()

    def __init__(self) -> None:
        """Initialize queue as a schema in in-memory SQLite database."""
        self._init_schema()

    def enqueue(self, qt: QueuedTask) -> None:
        """Persist a task inside SQLite while preserving ETA ordering."""
        if qt.eta is None:
            eta_value = None
        else:
            assert isinstance(qt.eta, datetime), "Must be datetime for ETA at this point"
            eta_value = qt.eta.isoformat()

        self.sqlite_connection.execute(
            """
            INSERT OR REPLACE INTO queue
            (id, task_name, args, kwargs, queue_name, enqueued_at, eta, exclusive)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                str(qt.id),
                qt.task_name,
                json.dumps(qt.args),
                json.dumps(qt.kwargs),
                qt.queue_name,
                qt.enqueued_at.isoformat(),
                eta_value,
                int(qt.exclusive),
            ),
        )
        self.sqlite_connection.commit()

    def dequeue(self, queue_name: str = TLO_DEFAULT_QUEUE_NAME) -> QueuedTask:
        """Return and remove the next eligible task for the provided queue."""
        now = datetime.now(timezone.utc).isoformat()
        cursor = self.sqlite_connection.execute(
            """
            SELECT id, task_name, args, kwargs, queue_name, enqueued_at, eta, exclusive
            FROM queue
            WHERE queue_name = ? AND (eta IS NULL OR eta <= ?)
            ORDER BY
                CASE WHEN eta IS NULL THEN 0 ELSE 1 END,  -- no-ETA first
                eta ASC
                LIMIT 1
            """,
            (queue_name, now),
        )
        row = cursor.fetchone()
        if not row:
            msg = "No eligible tasks in SQLite queue"
            raise NoTaskInQueueError(msg)

        task_id = row[0]
        self.sqlite_connection.execute("DELETE FROM queue WHERE id = ?", (task_id,))
        self.sqlite_connection.commit()

        return QueuedTask.from_sql_schema(row)

    def peek(self, queue_name: str = TLO_DEFAULT_QUEUE_NAME) -> QueuedTask | None:
        """Return the next eligible task without removing it from SQLite."""
        now = datetime.now(timezone.utc).isoformat()
        cursor = self.sqlite_connection.execute(
            """
            SELECT id, task_name, args, kwargs, queue_name, enqueued_at, eta, exclusive
            FROM queue
            WHERE queue_name = ? AND (eta IS NULL OR eta <= ?)
            ORDER BY
                CASE WHEN eta IS NULL THEN 0 ELSE 1 END,
                eta ASC
                LIMIT 1
            """,
            (queue_name, now),
        )
        row = cursor.fetchone()
        return QueuedTask.from_sql_schema(row) if row else None

    def remove(self, task_id: str) -> None:
        """Delete a task by ID regardless of its queue."""
        self.sqlite_connection.execute("DELETE FROM queue WHERE id = ?", (task_id,))
        self.sqlite_connection.commit()

    def __len__(self) -> int:
        """Return the total amount of rows stored in the backing table."""
        cursor = self.sqlite_connection.execute("SELECT COUNT(*) FROM queue")
        return int(cursor.fetchone()[0])

    def total_tasks_by_queue(self) -> dict[str, int]:
        """Return a mapping of queue_name → total number of tasks currently stored."""
        cursor = self.sqlite_connection.execute(
            """
            SELECT
                COALESCE(queue_name, 'default') AS queue_name,
                COUNT(*) AS count
            FROM queue
            GROUP BY queue_name
            """
        )
        return {row[0]: int(row[1]) for row in cursor.fetchall()}

    def total_tasks(self) -> int:
        """Return total number of tasks across all queues."""
        return len(self)
