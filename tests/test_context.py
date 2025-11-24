"""Tests for initializing core TLO services via context helpers."""

from tlo.common import SchedulerEnum
from tlo.context import (
    initialize_executor,
    initialize_locker,
    initialize_queue,
    initialize_scheduler,
    initialize_settings,
    initialize_task_registry,
    initialize_task_state_store,
)
from tlo.executor.executor import LocalExecutor


def test_initialize_defaults() -> None:
    """Ensure default initialization builds all runtime components."""
    settings = initialize_settings()
    task_registry = initialize_task_registry(settings)
    task_state_store = initialize_task_state_store(settings)
    queue = initialize_queue(settings)
    scheduler = initialize_scheduler(
        settings,
        registry=task_registry,
        queue=queue,
        state_store=task_state_store,
    )
    executor = initialize_executor(
        settings,
        registry=task_registry,
        state_store=task_state_store,
        queue=queue,
        scheduler=scheduler,
        locker=initialize_locker(settings),
    )

    assert scheduler is not None
    assert executor is not None
    assert queue is not None
    assert task_registry is not None
    assert task_state_store is not None


def test_initialize_custom() -> None:
    """Ensure non-default settings still produce valid instances."""
    # Just verifying we can pass different enums and it tries to load them
    # Since we only have one implementation of each for MVP, this is basic.
    settings = initialize_settings(
        scheduler=SchedulerEnum.SimpleScheduler,
        executor=LocalExecutor.get_name(),
    )
    task_registry = initialize_task_registry(settings)
    task_state_store = initialize_task_state_store(settings)
    queue = initialize_queue(settings)
    scheduler = initialize_scheduler(
        settings,
        registry=task_registry,
        queue=queue,
        state_store=task_state_store,
    )
    assert scheduler is not None


def test_initialize_executor_directly() -> None:
    """Ensure executor can be constructed directly from settings."""
    settings = initialize_settings()
    executor = initialize_executor(
        settings,
        registry=initialize_task_registry(settings),
        state_store=initialize_task_state_store(settings),
        queue=initialize_queue(settings),
        scheduler=initialize_scheduler(
            settings,
            registry=initialize_task_registry(settings),
            queue=initialize_queue(settings),
            state_store=initialize_task_state_store(settings),
        ),
        locker=initialize_locker(settings),
    )
    assert executor is not None
