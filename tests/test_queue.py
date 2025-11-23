"""Integration-style tests for all shipped queue implementations."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import time
from typing import TYPE_CHECKING

import pytest

from tlo.common import QueueEnum
from tlo.context import initialize_queue, initialize_settings
from tlo.errors import TloQueueEmptyError
from tlo.queue.queued_item import QueuedTask

if TYPE_CHECKING:
    from tlo.queue.queue import (
        QueueProtocol,
    )

QUEUE_IMPLEMENTATIONS = tuple(QueueEnum)


@pytest.fixture(params=QUEUE_IMPLEMENTATIONS)
def queue(request: pytest.FixtureRequest) -> QueueProtocol:
    """Return a fresh queue instance for every concrete implementation."""
    settings = initialize_settings(queue=request.param)
    return initialize_queue(settings)


def _make_task(
    task_id: str, *, queue_name: str = "default", eta: datetime | None = None
) -> QueuedTask:
    """Create QueuedTask objects with predictable defaults."""
    return QueuedTask(id=task_id, task_name="dummy_task", queue_name=queue_name, eta=eta)


def test_peek_matches_dequeue(queue: QueueProtocol) -> None:
    """Ensure peek returns same task as subsequent dequeue."""
    task = _make_task("task-no-eta")
    queue.enqueue(task)

    peeked = queue.peek()
    assert peeked == task
    assert queue.total_tasks() == 1

    dequeued = queue.dequeue()
    assert dequeued == task

    with pytest.raises(TloQueueEmptyError):
        queue.dequeue()


def test_enqueue_respects_eta_order(queue: QueueProtocol) -> None:
    """Verify ETA ordering is respected for dequeue eligibility."""
    now = datetime.now(timezone.utc)
    future_task = _make_task("future", eta=now + timedelta(seconds=30))
    immediate_task = _make_task("immediate")
    due_task = _make_task("due", eta=now - timedelta(seconds=30))

    queue.enqueue(future_task)
    queue.enqueue(immediate_task)
    queue.enqueue(due_task)

    assert queue.peek() == due_task
    assert queue.dequeue() == due_task
    assert queue.dequeue() == immediate_task

    with pytest.raises(TloQueueEmptyError):
        queue.dequeue()

    assert queue.peek() is None
    assert queue.total_tasks() == 1  # only the future task remains queued


def test_queue_name_routing_and_counts(queue: QueueProtocol) -> None:
    """Confirm queue names are isolated and per-queue counts stay accurate."""
    default_task = _make_task("default-task")
    priority_task = _make_task("priority-task", queue_name="priority")

    queue.enqueue(default_task)
    queue.enqueue(priority_task)

    assert queue.total_tasks() == 2
    counts = queue.total_tasks_by_queue()
    assert counts.get("default", 0) == 1
    assert counts.get("priority", 0) == 1

    dequeued_priority = queue.dequeue(queue_name="priority")
    assert dequeued_priority == priority_task

    with pytest.raises(TloQueueEmptyError):
        queue.dequeue(queue_name="priority")

    assert queue.peek(queue_name="default") == default_task

    queue.remove(default_task.id)
    assert queue.total_tasks() == 0
    assert queue.total_tasks_by_queue().get("default", 0) == 0


def test_remove_missing_task_raises(queue: QueueProtocol) -> None:
    """Removing unknown ids should raise to avoid silent failures."""
    task = _make_task("known")
    queue.enqueue(task)

    with pytest.raises(TloQueueEmptyError):
        queue.remove("missing")


def test_numeric_eta_is_normalised(queue: QueueProtocol) -> None:
    """Numeric ETA values should be converted to datetime on enqueue."""
    future_ts = time.time() + 5.5
    task = QueuedTask(task_name="numeric-eta", queue_name="default", eta=future_ts)

    queue.enqueue(task)

    stored = queue.dequeue_any_unsafe()
    assert isinstance(stored.eta, datetime)


def test_future_task_does_not_block_ready_task(queue: QueueProtocol) -> None:
    """Future ETA tasks should not block later ready tasks in same queue."""
    now = datetime.now(timezone.utc)
    future = QueuedTask(task_name="future", queue_name="default", eta=now + timedelta(hours=1))
    ready = QueuedTask(task_name="ready", queue_name="default", eta=now - timedelta(minutes=1))

    queue.enqueue(future)
    queue.enqueue(ready)

    dequeued = queue.dequeue()
    assert dequeued.task_name == "ready"
