"""Scheduler implementations for TLO."""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Protocol, runtime_checkable
import uuid

from tlo.common import SchedulerEnum
from tlo.errors import TloConfigError
from tlo.logging import WithLogger
from tlo.queue.queued_item import QueuedTask
from tlo.task_state_store.common import TaskStateRecord, TaskStatus
from tlo.utils import make_specific_register_func

if TYPE_CHECKING:
    from tlo.queue.queue import QueueProtocol
    from tlo.settings import TloSettings
    from tlo.task_registry.registry import TaskRegistryProtocol
    from tlo.task_state_store.state_store import TaskStateStoreProtocol

KNOWN_SCHEDULERS: dict[SchedulerEnum, type[SchedulerProtocol]] = {}
_register = make_specific_register_func(KNOWN_SCHEDULERS)


@runtime_checkable
class SchedulerProtocol(Protocol):
    """Protocol for scheduler implementations."""

    def tick(self) -> None:
        """Trigger a scheduling cycle."""

    def get_task_last_run(self, task_name: str) -> datetime | None:
        """Return the last time a task was run."""

    def set_task_last_run(self, task_name: str, last_run: datetime) -> None:
        """Record the last run time for a task."""


class AbstractScheduler(WithLogger, SchedulerProtocol, ABC):
    """Abstract base class for schedulers."""

    def __init__(
        self,
        registry: TaskRegistryProtocol,
        queue: QueueProtocol,
        state_store: TaskStateStoreProtocol,
        *,
        settings: TloSettings,
    ) -> None:
        """Initialize the scheduler.

        :param registry: The task registry to look up task definitions.
        :param queue: The queue to submit tasks to.
        :param state_store: The state store to persist queued task records.
        """
        self.registry = registry
        self.queue = queue
        self.state_store = state_store
        self.settings = settings

    @abstractmethod
    def tick(self) -> None:
        """Trigger a scheduling cycle."""

    @abstractmethod
    def get_task_last_run(self, task_name: str) -> datetime | None:
        """Return the last time a task was run."""

    @abstractmethod
    def set_task_last_run(self, task_name: str, last_run: datetime) -> None:
        """Record the last run time for a task."""


@_register(SchedulerEnum.SimpleScheduler)
class SimpleScheduler(AbstractScheduler):
    """A simple scheduler that checks for due tasks based on intervals."""

    def __init__(
        self,
        registry: TaskRegistryProtocol,
        queue: QueueProtocol,
        state_store: TaskStateStoreProtocol,
        *,
        settings: TloSettings,
    ) -> None:
        """Initialize the simple scheduler."""
        super().__init__(registry, queue, state_store, settings=settings)
        self._last_run: dict[str, datetime] = {}

    def get_task_last_run(self, task_name: str) -> datetime | None:
        """Return the last recorded run time for a task, if any."""
        return self._last_run.get(task_name)

    def set_task_last_run(self, task_name: str, last_run: datetime) -> None:
        """Record the last run time for a task."""
        self._last_run[task_name] = last_run

    def tick(self) -> None:
        """Check all registered tasks and enqueue them if they are due."""
        now = datetime.now(UTC)
        self._logger.debug("Scheduler tick at %s", now.isoformat())

        for task in self.registry.list_tasks():
            if task.schedule is None:
                self._logger.debug("Skipping unscheduled task %s", task.name)
                continue

            last_run = self.get_task_last_run(task.name)

            # If never run, run now.
            if last_run is None:
                should_run = True
            else:
                try:
                    next_run = task.schedule.next_run_after(last_run)
                    should_run = now >= next_run
                except TloConfigError:
                    raise
                except Exception:
                    if self.settings.panic_mode:
                        raise
                    self._logger.exception(
                        "Failed to compute schedule for task %s; skipping until next tick",
                        task.name,
                    )
                    continue

            if should_run:
                qt = QueuedTask(
                    id=str(uuid.uuid4()),
                    task_name=task.name,
                    queue_name=self.queue.default_queue,
                    exclusive_key=task.render_exclusive_key((), {}),
                )
                state_record = TaskStateRecord(
                    id=qt.id,
                    name=qt.task_name,
                    created_at=qt.enqueued_at,
                    created_by=self.__class__.__name__,
                    status=TaskStatus.Pending,
                )
                self.state_store.create(state_record)
                self.queue.enqueue(qt)
                self._logger.debug("Enqueued task %s (%s)", qt.task_name, qt.id)
                self.set_task_last_run(task.name, now)
