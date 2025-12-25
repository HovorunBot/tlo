"""Unit tests for scheduler logic and task enqueuing behaviour."""

from datetime import UTC, datetime, timedelta
from typing import cast

import pytest

from tlo.common import QueueEnum, SchedulerEnum, TaskRegistryEnum, TaskStateStoreEnum
from tlo.context import (
    initialize_queue,
    initialize_scheduler,
    initialize_settings,
    initialize_task_registry,
    initialize_task_state_store,
)
from tlo.errors import TloConfigError
from tlo.queue.queue import SimpleInMemoryQueue
from tlo.scheduler.scheduler import SimpleScheduler
from tlo.task_registry.registry import InMemoryTaskRegistry
from tlo.task_registry.task_def import IntervalSchedule, ScheduleProtocol
from tlo.task_state_store.common import TaskStateRecord, TaskStatus
from tlo.task_state_store.state_store import InMemoryTaskStateStore


def make_scheduler(
    *, panic_mode: bool = False
) -> tuple[SimpleScheduler, InMemoryTaskRegistry, SimpleInMemoryQueue, InMemoryTaskStateStore]:
    """Build scheduler with in-memory dependencies for tests."""
    settings = initialize_settings(
        task_registry=TaskRegistryEnum.InMemoryTaskRegistry,
        queue=QueueEnum.SimpleInMemoryQueue,
        task_state_store=TaskStateStoreEnum.InMemoryTaskStateStore,
        scheduler=SchedulerEnum.SimpleScheduler,
        panic_mode=panic_mode,
    )
    registry = initialize_task_registry(settings)
    queue = initialize_queue(settings)
    state_store = initialize_task_state_store(settings)
    scheduler = initialize_scheduler(settings, registry=registry, queue=queue, state_store=state_store)
    return (
        cast("SimpleScheduler", scheduler),
        cast("InMemoryTaskRegistry", registry),
        cast("SimpleInMemoryQueue", queue),
        cast("InMemoryTaskStateStore", state_store),
    )


def _register_task(registry: InMemoryTaskRegistry, name: str, schedule: ScheduleProtocol) -> None:
    @registry.register(name=name, schedule=schedule)
    def noop() -> None:
        return None


def test_tick_enqueues_due_tasks() -> None:
    """Tasks overdue for their interval should be enqueued."""
    scheduler, registry, queue, state_store = make_scheduler()
    _register_task(registry, "test_task", IntervalSchedule(timedelta(minutes=10)))

    # Pre-set last run to be older than interval
    scheduler.set_task_last_run("test_task", datetime.now(UTC) - timedelta(minutes=20))

    scheduler.tick()

    assert len(queue) == 1
    qt = queue.peek()
    assert qt is not None
    assert qt.task_name == "test_task"
    record = state_store.get(qt.id)
    assert isinstance(record, TaskStateRecord)
    assert record.status == TaskStatus.Pending


def test_tick_updates_last_run() -> None:
    """Tick should update last-run marker and avoid duplicate enqueues."""
    scheduler, registry, queue, _state_store = make_scheduler()
    _register_task(registry, "test_task", IntervalSchedule(timedelta(minutes=10)))

    # First run (never run before)
    scheduler.tick()

    first_run_time = scheduler.get_task_last_run("test_task")
    assert first_run_time is not None

    # Run again immediately - should not enqueue
    scheduler.tick()
    assert len(queue) == 1
    assert scheduler.get_task_last_run("test_task") == first_run_time


def test_tick_skips_future_tasks() -> None:
    """Skip enqueue when interval has not elapsed yet."""
    scheduler, registry, queue, _state_store = make_scheduler()
    _register_task(registry, "test_task", IntervalSchedule(timedelta(minutes=10)))

    # Last run was just now
    scheduler.set_task_last_run("test_task", datetime.now(UTC))

    scheduler.tick()

    assert len(queue) == 0


class BrokenSchedule(ScheduleProtocol):
    """Schedule implementation that always raises."""

    def next_run_after(self, last_run: datetime) -> datetime:
        """Raise an error to simulate faulty schedule."""
        _ = last_run
        msg = "Boom"
        raise ValueError(msg)


def test_tick_handles_errors() -> None:
    """Scheduler should swallow scheduling errors without enqueuing."""
    scheduler, registry, queue, _state_store = make_scheduler()
    _register_task(registry, "broken_task", BrokenSchedule())
    scheduler.set_task_last_run("broken_task", datetime.now(UTC))

    # Should not raise exception
    scheduler.tick()

    assert len(queue) == 0


class ConfigErrorSchedule(ScheduleProtocol):
    """Schedule implementation that raises configuration errors."""

    def next_run_after(self, last_run: datetime) -> datetime:
        """Raise TloConfigError to simulate misconfiguration."""
        _ = last_run
        msg = "config issue"
        raise TloConfigError(msg)


def test_tick_raises_on_config_error() -> None:
    """Configuration errors should propagate to fail fast."""
    scheduler, registry, queue, _state_store = make_scheduler()
    _register_task(registry, "broken_config_task", ConfigErrorSchedule())
    scheduler.set_task_last_run("broken_config_task", datetime.now(UTC))

    with pytest.raises(TloConfigError):
        scheduler.tick()

    assert len(queue) == 0


def test_tick_raises_on_unexpected_in_panic_mode() -> None:
    """Unexpected exceptions should bubble when panic_mode is enabled."""
    scheduler, registry, _queue, _state_store = make_scheduler(panic_mode=True)
    _register_task(registry, "panic_task", BrokenSchedule())
    scheduler.set_task_last_run("panic_task", datetime.now(UTC))

    with pytest.raises(ValueError, match="Boom"):
        scheduler.tick()
