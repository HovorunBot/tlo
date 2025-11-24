"""Tests for the executor behaviour and task state updates."""

from datetime import UTC, datetime, timedelta
from typing import NoReturn, cast

import pytest

from tlo.common import StopBehaviorEnum, TaskRegistryEnum
from tlo.context import (
    initialize_executor,
    initialize_locker,
    initialize_queue,
    initialize_scheduler,
    initialize_settings,
    initialize_task_registry,
    initialize_task_state_store,
)
from tlo.errors import TloQueueEmptyError
from tlo.executor.executor import LocalExecutor
from tlo.locking import InMemoryLocker
from tlo.queue.queued_item import QueuedTask
from tlo.task_registry.registry import InMemoryTaskRegistry
from tlo.task_state_store.common import TaskStateRecord, TaskStatus
from tlo.task_state_store.state_store import InMemoryTaskStateStore


@pytest.fixture
def context() -> tuple[InMemoryTaskRegistry, InMemoryTaskStateStore, LocalExecutor]:
    """Provide initialized registry, state store and executor for tests."""
    settings = initialize_settings(task_registry=TaskRegistryEnum.InMemoryTaskRegistry)
    registry = cast("InMemoryTaskRegistry", initialize_task_registry(settings))
    queue = initialize_queue(settings)
    state_store = cast("InMemoryTaskStateStore", initialize_task_state_store(settings))
    scheduler = initialize_scheduler(settings, registry=registry, queue=queue, state_store=state_store)
    locker = initialize_locker(settings)
    executor = cast(
        "LocalExecutor",
        initialize_executor(
            settings,
            registry=registry,
            state_store=state_store,
            queue=queue,
            scheduler=scheduler,
            locker=locker,
        ),
    )
    return registry, state_store, executor


def _seed_record(state_store: InMemoryTaskStateStore, qt: QueuedTask) -> None:
    """Persist a pending state record for the provided queued task."""
    record = TaskStateRecord(
        id=qt.id,
        name=qt.task_name,
        created_at=qt.enqueued_at,
        created_by="tests",
        status=TaskStatus.Pending,
    )
    state_store.create(record)


def test_execute_runs_task(
    context: tuple[InMemoryTaskRegistry, InMemoryTaskStateStore, LocalExecutor],
) -> None:
    """Executor should mark successful task runs as succeeded."""
    # Setup task
    registry, state_store, executor = context

    @registry.register(name="test_task")
    def sample_task() -> str:
        return "success"

    queued_task = QueuedTask(id="123", task_name="test_task", queue_name="default")
    _seed_record(state_store, queued_task)

    executor.execute(queued_task)

    updated = state_store.get("123")
    assert updated is not None
    assert updated.status == TaskStatus.Succeeded
    assert updated.result == "success"
    assert updated.finished_at is not None
    assert updated.started_at is not None


def test_execute_updates_state_failure(
    context: tuple[InMemoryTaskRegistry, InMemoryTaskStateStore, LocalExecutor],
) -> None:
    """Executor should mark failures and store exception text."""
    registry, state_store, executor = context

    @registry.register(name="fail_task")
    def failing_task() -> NoReturn:
        msg = "Failure"
        raise ValueError(msg)

    queued_task = QueuedTask(id="123", task_name="fail_task", queue_name="default")
    _seed_record(state_store, queued_task)

    executor.execute(queued_task)

    updated = state_store.get("123")
    assert updated is not None
    assert updated.status == TaskStatus.Failed
    assert "Failure" in str(updated.result)


def test_execute_handles_missing_task(
    context: tuple[InMemoryTaskRegistry, InMemoryTaskStateStore, LocalExecutor],
) -> None:
    """Missing task definitions should transition to failure state."""
    _, state_store, executor = context
    queued_task = QueuedTask(id="123", task_name="missing_task", queue_name="default")
    _seed_record(state_store, queued_task)

    executor.execute(queued_task)

    updated = state_store.get("123")
    assert updated is not None
    assert updated.status == TaskStatus.Failed
    assert "is not registered" in str(updated.result)


def test_execute_requeues_when_lock_contended() -> None:
    """Executor should requeue exclusive tasks when lock cannot be acquired."""
    settings = initialize_settings()
    registry = cast("InMemoryTaskRegistry", initialize_task_registry(settings))
    queue = initialize_queue(settings)
    state_store = cast("InMemoryTaskStateStore", initialize_task_state_store(settings))
    scheduler = initialize_scheduler(settings, registry=registry, queue=queue, state_store=state_store)
    locker = InMemoryLocker()
    executor = LocalExecutor(
        registry=registry,
        state_store=state_store,
        queue=queue,
        scheduler=scheduler,
        locker=locker,
        settings=settings,
    )

    @registry.register(name="exclusive_task", exclusive="entity-{entity_id}")
    def sample_task(*_: object, **__: object) -> str:
        return "ok"

    qt = QueuedTask(task_name="exclusive_task", queue_name=settings.default_queue, exclusive_key="entity-1")
    _seed_record(state_store, qt)
    assert locker.acquire("entity-1")

    executor.execute(qt)

    record = state_store.get(qt.id)
    assert record.status == TaskStatus.Pending
    assert queue.total_tasks() == 1
    assert locker.is_locked("entity-1")
    assert qt.eta is not None


def test_stop_cancel_pending_marks_cancelled(
    context: tuple[InMemoryTaskRegistry, InMemoryTaskStateStore, LocalExecutor],
) -> None:
    """stop(cancel=True) should cancel pending tasks."""
    registry, state_store, executor = context
    state = state_store

    @registry.register(name="noop")
    def noop() -> None:
        return None

    qt = QueuedTask(id="t1", task_name="noop", queue_name="default")
    _seed_record(state, qt)
    executor.queue.enqueue(qt)

    executor.stop(cancel=True)

    with pytest.raises(TloQueueEmptyError):
        executor.queue.dequeue()

    record = state.get(qt.id)
    assert record.status == TaskStatus.Cancelled


def test_stop_cancel_pending_removes_future_eta(
    context: tuple[InMemoryTaskRegistry, InMemoryTaskStateStore, LocalExecutor],
) -> None:
    """stop(cancel=True) should cancel tasks even if ETA is in the future."""
    registry, state_store, executor = context

    @registry.register(name="noop")
    def noop() -> None:
        return None

    future = datetime.now(UTC) + timedelta(hours=1)
    qt_future = QueuedTask(id="future", task_name="noop", queue_name="default", eta=future)
    _seed_record(state_store, qt_future)
    executor.queue.enqueue(qt_future)

    executor.stop(cancel=True)

    assert len(executor.queue) == 0
    record = state_store.get(qt_future.id)
    assert record.status == TaskStatus.Cancelled


def test_stop_cancel_pending_clears_all_queues(
    context: tuple[InMemoryTaskRegistry, InMemoryTaskStateStore, LocalExecutor],
) -> None:
    """stop(cancel=True) should cancel tasks across all queues."""
    registry, state_store, executor = context

    @registry.register(name="noop")
    def noop() -> None:
        return None

    qt_default = QueuedTask(id="dflt", task_name="noop", queue_name="default")
    qt_secondary = QueuedTask(id="sec", task_name="noop", queue_name="secondary")
    for qt in (qt_default, qt_secondary):
        _seed_record(state_store, qt)
        executor.queue.enqueue(qt)

    executor.stop(cancel=True)

    assert len(executor.queue) == 0
    assert state_store.get(qt_default.id).status == TaskStatus.Cancelled
    assert state_store.get(qt_secondary.id).status == TaskStatus.Cancelled


def test_stop_ignore_pending_leaves_queue(
    context: tuple[InMemoryTaskRegistry, InMemoryTaskStateStore, LocalExecutor],
) -> None:
    """Ignore should leave queued tasks untouched."""
    registry, state_store, executor = context
    executor.settings.stop_behavior = StopBehaviorEnum.Ignore

    @registry.register(name="noop")
    def noop() -> None:
        return None

    qt = QueuedTask(id="t2", task_name="noop", queue_name="default")
    _seed_record(state_store, qt)
    executor.queue.enqueue(qt)

    executor.stop()
    assert len(executor.queue) == 1


def test_stop_drain_pending_executes(
    context: tuple[InMemoryTaskRegistry, InMemoryTaskStateStore, LocalExecutor],
) -> None:
    """Drain should execute remaining tasks."""
    registry, state_store, executor = context
    executor.settings.stop_behavior = StopBehaviorEnum.Drain

    @registry.register(name="noop")
    def noop() -> str:
        return "ran"

    qt = QueuedTask(id="t3", task_name="noop", queue_name="default")
    _seed_record(state_store, qt)
    executor.queue.enqueue(qt)

    executor.stop()

    with pytest.raises(TloQueueEmptyError):
        executor.queue.dequeue()

    record = state_store.get(qt.id)
    assert record.status == TaskStatus.Succeeded
    assert record.result == "ran"


def test_stop_drain_pending_cancels_future_tasks(
    context: tuple[InMemoryTaskRegistry, InMemoryTaskStateStore, LocalExecutor],
) -> None:
    """Drain should cancel tasks with future ETA when stopping."""
    registry, state_store, executor = context
    executor.settings.stop_behavior = StopBehaviorEnum.Drain

    @registry.register(name="noop")
    def noop() -> None:
        return None

    future_eta = datetime.now(UTC) + timedelta(hours=1)
    future_task = QueuedTask(id="future-drain", task_name="noop", queue_name="default", eta=future_eta)
    _seed_record(state_store, future_task)
    executor.queue.enqueue(future_task)

    executor.stop()

    assert len(executor.queue) == 0
    record = state_store.get(future_task.id)
    assert record.status == TaskStatus.Cancelled


def test_drain_queue_processes_multiple_queues(
    context: tuple[InMemoryTaskRegistry, InMemoryTaskStateStore, LocalExecutor],
) -> None:
    """Drain should process tasks across all queues, not just default."""
    registry, state_store, executor = context
    executor.settings.stop_behavior = StopBehaviorEnum.Drain
    results: list[str] = []

    @registry.register(name="task_a")
    def task_a() -> str:
        results.append("A")
        return "A"

    @registry.register(name="task_b")
    def task_b() -> str:
        results.append("B")
        return "B"

    qt_a = QueuedTask(id="qa", task_name="task_a", queue_name="queue-a")
    qt_b = QueuedTask(id="qb", task_name="task_b", queue_name="queue-b")
    for qt in (qt_a, qt_b):
        _seed_record(state_store, qt)
        executor.queue.enqueue(qt)

    executor.stop()

    assert set(results) == {"A", "B"}
