"""Tests for the TLO orchestrator and task execution loop."""

from datetime import UTC, datetime, timedelta
import threading
import time

from tlo.orchestrator.orchestrator import Tlo


def test_submit_task_enqueues_real_queue() -> None:
    """submit_task should enqueue task with provided args/kwargs."""
    engine = Tlo(tick_interval=0.01)

    engine.submit_task("test_task", args=(1,), kwargs={"a": 2}, queue_name="priority")

    queued = engine.peek("priority")
    assert queued is not None
    assert queued.task_name == "test_task"
    assert queued.args == (1,)
    assert queued.kwargs == {"a": 2}
    assert queued.queue_name == "priority"


def test_reschedule_task_proxy() -> None:
    """reschedule_task should update ETA via the orchestrator."""
    engine = Tlo(tick_interval=0.01)
    engine.submit_task("first")
    engine.submit_task("second")

    tasks = engine.bulk_peek(limit=2)
    assert len(tasks) == 2

    first, second = tasks
    engine.reschedule_task(first.id, eta=datetime.now(UTC) + timedelta(hours=1))

    assert engine.peek() == second


def test_move_task_proxy() -> None:
    """move_task should re-route tasks between queues."""
    engine = Tlo(tick_interval=0.01)
    engine.submit_task("to-move")

    task = engine.peek()
    assert task is not None

    engine.move_task(task.id, queue_name="priority")

    assert engine.peek() is None
    moved = engine.peek(queue_name="priority")
    assert moved is not None
    assert moved.queue_name == "priority"


def test_engine_runs_registered_tasks() -> None:
    """Engine run loop should execute scheduled tasks."""
    engine = Tlo(tick_interval=0.01)
    results: list[str] = []

    @engine.register(name="ping", interval=timedelta(milliseconds=50))
    def ping_task() -> str:
        results.append("ping")
        return "ok"

    worker = threading.Thread(target=engine.run)
    worker.start()

    time.sleep(0.3)
    engine.stop()
    worker.join(timeout=1)

    assert results, "Engine did not execute scheduled task"


def test_engine_continues_after_executor_error() -> None:
    """Executor errors should not prevent subsequent tasks from running."""
    engine = Tlo(tick_interval=0.01)
    results: list[str] = []

    @engine.register(name="boom", interval=timedelta(milliseconds=30))
    def boom_task() -> None:
        msg = "boom"
        raise RuntimeError(msg)

    @engine.register(name="ok", interval=timedelta(milliseconds=30))
    def ok_task() -> str:
        results.append("ok")
        return "ok"

    worker = threading.Thread(target=engine.run)
    worker.start()

    time.sleep(0.4)
    engine.stop()
    worker.join(timeout=1)

    assert "ok" in results, "Engine did not continue executing after a failure"
