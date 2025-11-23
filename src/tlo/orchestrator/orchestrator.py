"""Orchestrator implementation for TLO."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from typing_extensions import Unpack

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
    from datetime import timedelta

    from tlo.settings import TloSettingsKwargs
    from tlo.task_registry.task_def import ScheduleProtocol
    from tlo.tlo_types import TTaskDecorator


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

    def submit_task(
        self,
        name: str,
        args: tuple[Any, ...] = (),
        kwargs: dict[str, Any] | None = None,
    ) -> None:
        """Enqueue a task for immediate execution with optional arguments."""
        if kwargs is None:
            kwargs = {}

        qt = QueuedTask(
            task_name=name, args=args, kwargs=kwargs, queue_name=self._settings.default_queue
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

    def run(self) -> None:
        """Run the executor loop synchronously."""
        self._executor.run()

    async def run_async(self) -> None:
        """Run the executor loop asynchronously when supported."""
        await self._executor.run_async()
