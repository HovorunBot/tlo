"""Data object and functionality related to queued task specification."""

import dataclasses
from datetime import datetime, timezone
import json
from typing import Any

from typing_extensions import LiteralString

from tlo.common import TLO_DEFAULT_QUEUE_NAME
from tlo.tlo_types import FuncName, TaskId


@dataclasses.dataclass(slots=True)
class QueuedTask:
    """Represents a task scheduled for immediate or delayed execution.

    :param id: Unique identifier of the task instance.
    :param task_name: Name of the task registered in
        :class:`~tlo.task_registry.registry.TaskRegistryProtocol`.
    :param args: Positional arguments passed to the task.
    :param kwargs: Keyword arguments passed to the task.
    :param queue_name: Name of the logical queue this task belongs to.
    :param enqueued_at: Timestamp of when the task was placed into the queue.
    :param eta: Optional timestamp describing when the task becomes eligible.
        ``None`` means the task is ready immediately.
    :param exclusive: If ``True``, execution of this task must be exclusive
    """

    id: TaskId
    task_name: FuncName
    args: tuple[Any, ...] = dataclasses.field(default_factory=tuple)
    kwargs: dict[str, Any] = dataclasses.field(default_factory=dict)
    queue_name: str = TLO_DEFAULT_QUEUE_NAME
    enqueued_at: datetime = dataclasses.field(default_factory=lambda: datetime.now(timezone.utc))
    eta: datetime | int | None = None
    exclusive: bool = False

    def __post_init__(self) -> None:
        """Normalise ETA values provided as integers to ``datetime``."""
        if isinstance(self.eta, int):
            self.eta = datetime.fromtimestamp(self.eta, timezone.utc)

    @classmethod
    def to_sql_table(cls) -> LiteralString:
        """Return SQL required to create the backing table for queued tasks."""
        return """
CREATE TABLE IF NOT EXISTS queue (
     id TEXT PRIMARY KEY,
     task_name TEXT NOT NULL,
     args TEXT,
     kwargs TEXT,
     queue_name TEXT,
     enqueued_at TEXT NOT NULL,
     eta TEXT,
     exclusive INTEGER NOT NULL DEFAULT 0
)
"""

    @classmethod
    def from_sql_schema(cls, row: tuple[str, str, str, str, str, str, str, int]) -> "QueuedTask":
        """Return a queued task restored from a SQL row retrieved via :meth:`to_sql_table`."""
        return cls(
            id=row[0],
            task_name=row[1],
            args=tuple(json.loads(row[2] or "[]")),
            kwargs=json.loads(row[3] or "{}"),
            queue_name=row[4],
            enqueued_at=datetime.fromisoformat(row[5]),
            eta=datetime.fromisoformat(row[6]) if row[6] else None,
            exclusive=bool(row[7]),
        )
