"""Data object and functionality related to queued task specification."""

import dataclasses
from datetime import UTC, datetime
from typing import Any
import uuid

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

    task_name: FuncName
    queue_name: str
    id: TaskId = dataclasses.field(default_factory=lambda: str(uuid.uuid4()))
    args: tuple[Any, ...] = dataclasses.field(default_factory=tuple)
    kwargs: dict[str, Any] = dataclasses.field(default_factory=dict)
    enqueued_at: datetime = dataclasses.field(default_factory=lambda: datetime.now(UTC))
    eta: datetime | int | float | None = None
    exclusive_key: str | None = None

    def __post_init__(self) -> None:
        """Normalise ETA values provided as integers to ``datetime``."""
        if isinstance(self.eta, (int, float)):
            self.eta = datetime.fromtimestamp(self.eta, UTC)
