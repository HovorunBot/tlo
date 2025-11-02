"""Tests covering the behaviour of the task registry utilities."""

from __future__ import annotations

from datetime import timedelta

from tlo.task_registry.registry import TaskRegistry


def test_register_uses_function_name_and_preserves_callable() -> None:
    """Register decorator should fall back to the callable name and return the original function."""
    registry = TaskRegistry()

    @registry.register()
    def sample_task() -> str:
        return "ok"

    assert "sample_task" in registry
    task = registry.get_task("sample_task")
    assert task.func() == "ok"
    assert task.interval is None
    assert task.extra == {}


def test_register_supports_custom_name_interval_and_metadata() -> None:
    """Registration should accept overrides for name, interval, and metadata."""
    registry = TaskRegistry()

    @registry.register(name="custom", interval=30, extra={"source": "tests"})
    def sample_task() -> None:
        return None

    assert "custom" in registry
    task = registry["custom"]
    assert task.func is sample_task
    assert task.interval == timedelta(seconds=30)
    assert task.extra == {"source": "tests"}


def test_register_accepts_timedelta_interval() -> None:
    """Registration should accept an explicit ``timedelta`` interval."""
    registry = TaskRegistry()

    interval = timedelta(minutes=5)

    @registry.register(interval=interval)
    def sample_task() -> None:
        return None

    assert registry.get_task("sample_task").interval == interval


def test_list_helpers_return_expected_values() -> None:
    """The helper methods should expose the stored definitions and their names."""
    registry = TaskRegistry()

    @registry.register()
    def first() -> None:
        return None

    @registry.register(name="second")
    def other() -> None:
        return None

    names = registry.list_task_names()
    assert names == ["first", "second"]

    tasks = registry.list_tasks()
    assert [task.name for task in tasks] == ["first", "second"]
    assert all(callable(task.func) for task in tasks)
