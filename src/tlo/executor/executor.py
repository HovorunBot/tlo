"""Executor implementations for TLO."""

from __future__ import annotations

from abc import ABC, abstractmethod
import asyncio
from datetime import datetime, timezone
import inspect
import time
from typing import TYPE_CHECKING, Any, ClassVar, Protocol, TypeVar, runtime_checkable

from typing_extensions import assert_never

from tlo.common import ExecutorEnum, StopBehaviorEnum
from tlo.errors import TloQueueEmptyError
from tlo.task_state_store.common import TaskStateRecord, TaskStatus
from tlo.utils import make_specific_register_func

if TYPE_CHECKING:
    from collections.abc import Awaitable

    from tlo.queue.queue import QueueProtocol
    from tlo.queue.queued_item import QueuedTask
    from tlo.scheduler.scheduler import SchedulerProtocol
    from tlo.settings import TloSettings
    from tlo.task_registry.registry import TaskRegistryProtocol
    from tlo.task_state_store.state_store import TaskStateStoreProtocol

KNOWN_EXECUTORS: dict[ExecutorEnum, type[ExecutorProtocol]] = {}
_register = make_specific_register_func(KNOWN_EXECUTORS)

T_co = TypeVar("T_co", covariant=True)

_SENTINEL: Any = object()


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


class AbstractExecutor(ExecutorProtocol, ABC):
    """Abstract base class handling task state transitions."""

    asynchronous: ClassVar[bool] = _SENTINEL

    def __init_subclass__(cls, **kwargs: Any) -> None:
        """Ensure that subclasses specify `asynchronous` class attribute."""
        super().__init_subclass__(**kwargs)
        if cls.asynchronous is _SENTINEL:
            msg = f"{cls.__name__!r} must specify `asynchronous` class attribute"
            raise NotImplementedError(msg)

    def __init__(
        self,
        registry: TaskRegistryProtocol,
        state_store: TaskStateStoreProtocol,
        queue: QueueProtocol,
        scheduler: SchedulerProtocol,
        settings: TloSettings,
    ) -> None:
        """Initialize the executor."""
        self.registry = registry
        self.state_store = state_store
        self.queue = queue
        self.scheduler = scheduler
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

    @classmethod
    def get_name(cls) -> ExecutorEnum:
        """Return the registry key for this executor based on its class name."""
        return ExecutorEnum(cls.__name__)

    def _start(self) -> None:
        """Mark executor as running."""
        self._running = True

    def _get_record(self, task: QueuedTask) -> TaskStateRecord:
        return self.state_store.get(task.id)

    def _mark_running(self, record: TaskStateRecord) -> None:
        now = datetime.now(timezone.utc)
        record.started_at = record.started_at or now
        record.status = TaskStatus.Running
        self.state_store.update(record)

    def _mark_succeeded(self, record: TaskStateRecord, result: object) -> None:
        finished_at = datetime.now(timezone.utc)
        record.finished_at = finished_at
        record.status = TaskStatus.Succeeded
        record.result = result
        self.state_store.update(record)

    def _mark_failed(self, record: TaskStateRecord, exc: Exception) -> None:
        finished_at = datetime.now(timezone.utc)
        record.finished_at = finished_at
        record.status = TaskStatus.Failed
        record.result = str(exc)
        self.state_store.update(record)


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
            while self._running:
                self.scheduler.tick()
                self._drain_queue()
                time.sleep(self.settings.tick_interval)
        finally:
            self._running = False

    async def run_async(self) -> None:
        """Run the executor loop asynchronously.

        Not supported by LocalExecutor.
        """
        msg = "LocalExecutor does not support asynchronous execution"
        raise TypeError(msg)

    def execute(self, task: QueuedTask) -> None:
        """Execute a single queued task and update its state record."""
        record = self._get_record(task)
        self._mark_running(record)
        try:
            task_def = self.registry.get_task(task.task_name)
            result = task_def.func(*task.args, **task.kwargs)
            if inspect.isawaitable(result):
                coroutine = result if inspect.iscoroutine(result) else _await_awaitable(result)
                result = asyncio.run(coroutine)
        except Exception as exc:  # noqa: BLE001
            self._mark_failed(record, exc)
            return

        self._mark_succeeded(record, result)

    async def execute_async(self, _task: QueuedTask) -> None:
        """Execute a single queued task asynchronously.

        Not supported by LocalExecutor.
        """
        msg = "LocalExecutor does not support asynchronous execution"
        raise TypeError(msg)

    @property
    def is_running(self) -> bool:
        """Return True while the executor loop is active."""
        return self._running

    def stop(self, *, cancel: bool = False) -> None:
        """Stop the executor loop and optionally clear pending tasks."""
        self._running = False
        self._handle_stop_pending(cancel_requested=cancel)

    def _handle_stop_pending(self, *, cancel_requested: bool) -> None:
        """Handle queued tasks when stopping based on configured behaviour."""
        behavior = StopBehaviorEnum.Cancel if cancel_requested else self.settings.stop_behavior

        match behavior:
            case StopBehaviorEnum.Cancel:
                self._cancel_pending_tasks()
            case StopBehaviorEnum.Ignore:
                return
            case StopBehaviorEnum.Drain:
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
                finished_at = datetime.now(timezone.utc)
                record.finished_at = finished_at
                record.status = TaskStatus.Cancelled
                self.state_store.update(record)
                made_progress = True

            if not made_progress:
                return

    def _drain_queue(self) -> None:
        """Execute all ready tasks in the queue."""
        while True:
            try:
                task = self.queue.dequeue()
            except TloQueueEmptyError:
                return
            self.execute(task)
