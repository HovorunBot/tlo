"""Executor should handle async task functions."""

from __future__ import annotations

import asyncio

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


def test_local_executor_runs_async_tasks() -> None:
    """Ensure async tasks are awaited and completed by LocalExecutor."""
    settings = initialize_settings()
    registry = initialize_task_registry(settings)
    state_store = initialize_task_state_store(settings)
    queue = initialize_queue(settings)
    scheduler = initialize_scheduler(settings, registry=registry, queue=queue, state_store=state_store)
    executor = initialize_executor(
        settings, registry=registry, state_store=state_store, queue=queue, scheduler=scheduler
    )

    @registry.register()
    async def async_task() -> str:
        await asyncio.sleep(0)
        return "ok"

    qt = QueuedTask(task_name="async_task", queue_name=settings.default_queue)
    state_store.create(
        TaskStateRecord(
            id=qt.id,
            name=qt.task_name,
            created_at=qt.enqueued_at,
            created_by="test",
            status=TaskStatus.Pending,
        )
    )
    queue.enqueue(qt)

    task = queue.dequeue()
    executor.execute(task)

    record = state_store.get(task.id)
    assert record.status == TaskStatus.Succeeded
    assert record.result == "ok"
