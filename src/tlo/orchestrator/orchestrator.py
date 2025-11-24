"""Orchestrator implementation for TLO."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Unpack

from tlo.context import (
    initialize_executor,
    initialize_queue,
    initialize_scheduler,
    initialize_settings,
    initialize_task_registry,
    initialize_task_state_store,
)
from tlo.queue.queued_item import QueuedTask
from tlo.task_state_store.common import TaskStateRecord, TaskStatus

if TYPE_CHECKING:
    from datetime import datetime, timedelta

    from tlo.settings import TloSettingsKwargs
    from tlo.task_registry.task_def import ScheduleProtocol
    from tlo.tlo_types import TaskId, TTaskDecorator


class Tlo:
    """Single orchestrator that delegates execution to an executor."""

    def __init__(self, **settings: Unpack[TloSettingsKwargs]) -> None:
        """Initialize the orchestrator with the given settings."""
        resolved_settings = initialize_settings(**settings)

        self._settings = resolved_settings
        self._task_registry = initialize_task_registry(resolved_settings)
        self._task_state_store = initialize_task_state_store(resolved_settings)
        self._queue = initialize_queue(resolved_settings)
        self._scheduler = initialize_scheduler(
            resolved_settings,
            registry=self._task_registry,
            queue=self._queue,
            state_store=self._task_state_store,
        )
        self._executor = initialize_executor(
            resolved_settings,
            registry=self._task_registry,
            state_store=self._task_state_store,
            queue=self._queue,
            scheduler=self._scheduler,
        )

    @property
    def is_running(self) -> bool:
        """Return status of the executor process."""
        return self._executor.is_running

    def register(
        self,
        name: str | None = None,
        *,
        interval: int | timedelta | None = None,
        cron: str | None = None,
        schedule: ScheduleProtocol | None = None,
        extra: dict[str, Any] | None = None,
    ) -> TTaskDecorator:
        """Register a callable as a task and return a decorator wrapper."""
        return self._task_registry.register(
            name=name,
            interval=interval,
            cron=cron,
            schedule=schedule,
            extra=extra,
        )

    def stop(self, *, cancel: bool = False) -> None:
        """Stop task processing and optionally clear queued tasks."""
        self._executor.stop(cancel=cancel)

    def submit_task(  # noqa: PLR0913
        self,
        name: str,
        args: tuple[Any, ...] = (),
        kwargs: dict[str, Any] | None = None,
        *,
        queue_name: str | None = None,
        eta: datetime | float | None = None,
        exclusive: bool = False,
    ) -> None:
        """Enqueue a task for immediate execution with optional arguments."""
        if kwargs is None:
            kwargs = {}

        qt = QueuedTask(
            task_name=name,
            args=args,
            kwargs=kwargs,
            queue_name=queue_name or self._settings.default_queue,
            eta=eta,
            exclusive=exclusive,
        )
        task_record = TaskStateRecord(
            id=qt.id,
            name=qt.task_name,
            created_at=qt.enqueued_at,
            created_by=self.__class__.__name__,
            status=TaskStatus.Pending,
        )
        self._task_state_store.create(task_record)
        self._queue.enqueue(qt)

    def peek(self, queue_name: str | None = None) -> QueuedTask | None:
        """Return the next eligible task without removing it from the queue."""
        return self._queue.peek(queue_name)

    def bulk_peek(self, queue_name: str | None = None, *, limit: int | None = None) -> list[QueuedTask]:
        """Return up to *limit* eligible tasks without removing them."""
        return self._queue.bulk_peek(queue_name, limit=limit)

    def reschedule_task(self, task_id: TaskId, *, eta: datetime | float | None) -> None:
        """Update ETA for a queued task."""
        self._queue.reschedule(task_id, eta=eta)

    def move_task(self, task_id: TaskId, *, queue_name: str) -> None:
        """Move a queued task to another queue."""
        self._queue.move(task_id, queue_name=queue_name)

    def run(self) -> None:
        """Run the executor loop synchronously."""
        self._executor.run()

    async def run_async(self) -> None:
        """Run the executor loop asynchronously when supported."""
        await self._executor.run_async()
