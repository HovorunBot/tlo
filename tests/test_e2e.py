"""End-to-end test covering task registration and execution flow."""

from datetime import timedelta
import threading
import time

from tlo.orchestrator.orchestrator import Tlo


def test_e2e_flow() -> None:
    """Test that simpliest execution workflow."""
    # Inject our registry into the context
    # Shared state for the test task
    result_box = []

    engine = Tlo(tick_interval=0.1)

    @engine.register(name="e2e_task", interval=timedelta(milliseconds=100))
    def e2e_task(arg: str) -> str:
        result_box.append(arg)
        return "done"

    @engine.register(name="e2e_task_ctx", interval=timedelta(milliseconds=100))
    def e2e_task_ctx(arg: str | None = None) -> None:
        result_box.append(arg or "scheduled")

    # Run orchestrator in a separate thread to avoid thread blocking.
    # You can stop execution by calling engine.stop() in any thread.
    t = threading.Thread(target=engine.run)
    t.start()

    try:
        # Ensure that runner tick happens the at least single time
        time.sleep(0.5)

        # Verify that a task has been executed by the executor
        assert len(result_box) > 0, f"Task did not run. RESULT_BOX: {result_box}"
        assert result_box[0] is not None

        # Also test manual submission
        engine.submit_task("e2e_task_ctx", args=("manual",))
        time.sleep(0.5)
        assert "manual" in result_box

    finally:
        engine.stop()
        t.join(timeout=2)
