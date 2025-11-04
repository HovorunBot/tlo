"""Integration-style tests for all shipped queue implementations."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from tlo.errors import NoTaskInQueueError
from tlo.queue.queue import (
    InMemorySqliteQueue,
    MapQueue,
    QueueProtocol,
    SimpleInMemoryQueue,
)
from tlo.queue.queued_item import QueuedTask

QUEUE_IMPLEMENTATIONS = (
    SimpleInMemoryQueue,
    MapQueue,
    InMemorySqliteQueue,
)


@pytest.fixture(params=QUEUE_IMPLEMENTATIONS)
def queue(request: pytest.FixtureRequest) -> QueueProtocol:
    """Return a fresh queue instance for every concrete implementation."""
    queue_class = request.param
    queue_obj: QueueProtocol = queue_class()
    if isinstance(queue_obj, InMemorySqliteQueue):
        queue_obj.sqlite_connection.execute("DELETE FROM queue")
        queue_obj.sqlite_connection.commit()
    return queue_obj


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

    with pytest.raises(NoTaskInQueueError):
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

    assert queue.peek() == immediate_task
    assert queue.dequeue() == immediate_task
    assert queue.dequeue() == due_task

    with pytest.raises(NoTaskInQueueError):
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

    with pytest.raises(NoTaskInQueueError):
        queue.dequeue(queue_name="priority")

    assert queue.peek(queue_name="default") == default_task

    queue.remove(default_task.id)
    assert queue.total_tasks() == 0
    assert queue.total_tasks_by_queue().get("default", 0) == 0
