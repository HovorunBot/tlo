"""Executor implementations for TLO."""

from __future__ import annotations

from abc import ABC, abstractmethod
import asyncio
from datetime import UTC, datetime, timedelta
import inspect
import time
from typing import TYPE_CHECKING, Any, ClassVar, Protocol, TypeVar, assert_never, runtime_checkable

from hv_utils.sentinel import MISSING

from tlo.common import ExecutorEnum, StopBehaviorEnum
from tlo.errors import TloQueueEmptyError
from tlo.logging import WithLogger
from tlo.task_state_store.common import TaskStateRecord, TaskStatus
from tlo.utils import make_specific_register_func

if TYPE_CHECKING:
    from collections.abc import Awaitable

    from tlo.locking import LockerProtocol
    from tlo.queue.queue import QueueProtocol
    from tlo.queue.queued_item import QueuedTask
    from tlo.scheduler.scheduler import SchedulerProtocol
    from tlo.settings import TloSettings
    from tlo.task_registry.registry import TaskRegistryProtocol
    from tlo.task_state_store.state_store import TaskStateStoreProtocol
    from tlo.tlo_types import TaskId

KNOWN_EXECUTORS: dict[ExecutorEnum, type[ExecutorProtocol]] = {}
_register = make_specific_register_func(KNOWN_EXECUTORS)

T_co = TypeVar("T_co", covariant=True)


@runtime_checkable
class ExecutorProtocol(Protocol):
    """Interface for executor implementations."""

    asynchronous: ClassVar[bool]
    """Specifies whether the orchestrator loop should run asynchronously."""

    def run(self) -> None:
        """Run task loop synchronously."""

    async def run_async(self) -> None:
        """Run the task loop asynchronously."""

    @property
    def is_running(self) -> bool:
        """Return status of the executor process."""

    def _start(self) -> None:
        """Set up the executor loop to start.

        It is not expected to be called directly by code, but by `run` or `run_async` functions.
        """

    def stop(self, *, cancel: bool = False) -> None:
        """Stop the executor loop."""

    def execute(self, task: QueuedTask) -> None:
        """Execute a single queued task synchronously."""

    async def execute_async(self, task: QueuedTask) -> None:
        """Execute a single queued task asynchronously."""

    def stop_task(self, task_id: TaskId) -> TaskStateRecord:
        """Attempt to stop/kill a specific task and return its final state."""

    def get_task_state(self, task_id: TaskId) -> TaskStateRecord:
        """Return execution state for a specific task."""


class AbstractExecutor(WithLogger, ExecutorProtocol, ABC):
    """Abstract base class handling task state transitions."""

    asynchronous: ClassVar[bool] = MISSING

    def __init_subclass__(cls, **kwargs: Any) -> None:
        """Ensure that subclasses specify `asynchronous` class attribute."""
        super().__init_subclass__(**kwargs)
        if cls.asynchronous is MISSING:
            msg = f"{cls.__name__!r} must specify `asynchronous` class attribute"
            raise NotImplementedError(msg)

    def __init__(
        self,
        registry: TaskRegistryProtocol,
        state_store: TaskStateStoreProtocol,
        queue: QueueProtocol,
        scheduler: SchedulerProtocol,
        locker: LockerProtocol,
        settings: TloSettings,
    ) -> None:
        """Initialize the executor."""
        self.registry = registry
        self.state_store = state_store
        self.queue = queue
        self.scheduler = scheduler
        self.locker = locker
        self.settings = settings
        self._running = False

    @abstractmethod
    def run(self) -> None:
        """Run the executor loop."""

    @abstractmethod
    async def run_async(self) -> None:
        """Run the executor loop asynchronously."""

    @abstractmethod
    def execute(self, task: QueuedTask) -> None:
        """Execute a single queued task synchronously."""

    @abstractmethod
    async def execute_async(self, task: QueuedTask) -> None:
        """Execute a single queued task asynchronously."""

    @abstractmethod
    def stop_task(self, task_id: TaskId) -> TaskStateRecord:
        """Attempt to stop a running task by id."""

    def get_task_state(self, task_id: TaskId) -> TaskStateRecord:
        """Return the latest stored state for *task_id*."""
        return self.state_store.get(task_id)

    @classmethod
    def get_name(cls) -> ExecutorEnum:
        """Return the registry key for this executor based on its class name."""
        return ExecutorEnum(cls.__name__)

    def _start(self) -> None:
        """Mark executor as running."""
        self._running = True
        self._logger.debug("Executor %s started", self.__class__.__name__)

    def _get_record(self, task: QueuedTask) -> TaskStateRecord:
        return self.state_store.get(task.id)

    def _mark_running(self, record: TaskStateRecord) -> None:
        now = datetime.now(UTC)
        record.started_at = record.started_at or now
        record.status = TaskStatus.Running
        self.state_store.update(record)
        self._logger.debug("Marked task %s as running", record.id)

    def _mark_succeeded(self, record: TaskStateRecord, result: object) -> None:
        finished_at = datetime.now(UTC)
        record.finished_at = finished_at
        record.status = TaskStatus.Succeeded
        record.result = result
        self.state_store.update(record)
        self._logger.debug("Task %s succeeded", record.id)

    def _mark_failed(self, record: TaskStateRecord, exc: Exception) -> None:
        finished_at = datetime.now(UTC)
        record.finished_at = finished_at
        record.status = TaskStatus.Failed
        record.result = str(exc)
        self.state_store.update(record)
        self._logger.error("Task %s failed with exception", record.id, exc_info=exc)


async def _await_awaitable(awaitable: Awaitable[Any]) -> Any:
    """Await any awaitable and return its result."""
    return await awaitable


@_register(ExecutorEnum.LocalExecutor)
class LocalExecutor(AbstractExecutor):
    """Run tasks synchronously in the local process."""

    asynchronous = False

    def run(self) -> None:
        """Continuously tick the scheduler and drain the queue."""
        self._start()
        try:
            self._logger.debug(
                "Running LocalExecutor loop (tick_interval=%s, default_queue=%s)",
                self.settings.tick_interval,
                self.queue.default_queue,
            )
            while self._running:
                self.scheduler.tick()
                self._drain_queue()
                time.sleep(self.settings.tick_interval)
        finally:
            self._running = False
            self._logger.debug("LocalExecutor loop stopped")

    async def run_async(self) -> None:
        """Run the executor loop asynchronously.

        Not supported by LocalExecutor.
        """
        msg = "LocalExecutor does not support asynchronous execution"
        raise TypeError(msg)

    def _execute_task(self, task: QueuedTask, record: TaskStateRecord) -> None:
        """Execute task and update state record."""
        self._mark_running(record)
        try:
            self._logger.debug("Executing task %s (%s)", task.task_name, task.id)
            task_def = self.registry.get_task(task.task_name)
            result = task_def.func(*task.args, **task.kwargs)
            if inspect.isawaitable(result):
                coroutine = result if inspect.iscoroutine(result) else _await_awaitable(result)
                result = asyncio.run(coroutine)
        except Exception as exc:  # noqa: BLE001
            self._mark_failed(record, exc)
            return

        self._mark_succeeded(record, result)
        self._logger.debug("Finished task %s (%s)", task.task_name, task.id)

    def execute(self, task: QueuedTask) -> None:
        """Execute a single queued task and update its state record."""
        record = self._get_record(task)
        lock_key = task.exclusive_key
        guard = self.locker.guard(lock_key) if lock_key is not None else None
        if guard is not None:
            with guard as acquired:
                if not acquired:
                    retry_eta = datetime.now(UTC) + timedelta(seconds=self.settings.tick_interval)
                    task.eta = retry_eta
                    self.queue.enqueue(task)
                    self._logger.debug("Could not acquire lock %s for task %s; requeued", lock_key, task.id)
                    return
                self._execute_task(task, record)
        else:
            self._execute_task(task, record)

    async def execute_async(self, task: QueuedTask) -> None:
        """Execute a single queued task asynchronously.

        Not supported by LocalExecutor.
        """
        _ = task
        msg = "LocalExecutor does not support asynchronous execution"
        raise TypeError(msg)

    def stop_task(self, task_id: TaskId) -> TaskStateRecord:
        """LocalExecutor cannot stop a task mid-execution due to synchronous model."""
        _ = task_id
        msg = (
            f"{self.__class__.__name__!r} does not support stop_task functionality as implementation is synchronous "
            f"and single threaded."
        )
        raise TypeError(msg)

    @property
    def is_running(self) -> bool:
        """Return True while the executor loop is active."""
        return self._running

    def stop(self, *, cancel: bool = False) -> None:
        """Stop the executor loop and optionally clear pending tasks."""
        self._running = False
        self._logger.debug("Stopping executor cancel=%s", cancel)
        self._handle_stop_pending(cancel_requested=cancel)

    def _handle_stop_pending(self, *, cancel_requested: bool) -> None:
        """Handle queued tasks when stopping based on configured behaviour."""
        behavior = StopBehaviorEnum.Cancel if cancel_requested else self.settings.stop_behavior

        match behavior:
            case StopBehaviorEnum.Cancel:
                self._logger.debug("Cancelling pending tasks on stop")
                self._cancel_pending_tasks()
            case StopBehaviorEnum.Ignore:
                self._logger.debug("Ignoring pending tasks on stop")
                return
            case StopBehaviorEnum.Drain:
                self._logger.debug("Draining queue before stopping")
                self._drain_queue()
                self._cancel_pending_tasks()
            case _:
                assert_never(behavior)

    def _cancel_pending_tasks(self) -> None:
        """Mark queued tasks as cancelled without executing them."""
        while True:
            queues = self.queue.total_tasks_by_queue()
            if not queues:
                return

            made_progress = False
            for queue_name, count in list(queues.items()):
                if count == 0:
                    continue
                try:
                    task = self.queue.dequeue_any_unsafe(queue_name)
                except TloQueueEmptyError:
                    continue

                record = self._get_record(task)
                finished_at = datetime.now(UTC)
                record.finished_at = finished_at
                record.status = TaskStatus.Cancelled
                self.state_store.update(record)
                self._logger.debug("Cancelled task %s from queue %s", task.id, queue_name)
                made_progress = True

            if not made_progress:
                return

    def _drain_queue(self) -> None:
        """Execute all ready tasks across available queues."""
        while True:
            queues = self.queue.total_tasks_by_queue()
            if not queues:
                return

            made_progress = False
            for queue_name, count in list(queues.items()):
                if count == 0:
                    continue
                try:
                    task = self.queue.dequeue(queue_name)
                except TloQueueEmptyError:
                    continue
                self.execute(task)
                made_progress = True

            if not made_progress:
                return
