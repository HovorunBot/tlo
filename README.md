# TLO

> **Warning:** TLO is currently in a pre-alpha stage. Public APIs and overall behaviour may change without notice until
> the first stable release.

TLO (Task Layer Operations) is a lightweight, modular toolkit for defining and running background tasks — without
committing to a full-fledged scheduler from the start. It provides a minimal registry for task definitions, strongly
typed interfaces, and pluggable state storage, enabling you to prototype background workloads quickly and evolve them
into more complex systems over time.

The name TLO comes from the Ukrainian word “тло” (tlo), meaning “background” — a nod to its focus on reliable,
behind-the-scenes task execution.

Install with `pip install tlo-runner`. Import the package as `tlo`.

## Key Features

- Minimal, decorator-driven API for registering recurring async or sync callables.
- In-memory reference implementations (registry, queues, state store) that work immediately for prototypes and tests.
- Protocol-based registry, queue, and state-store contracts that are easy to replace with your own services.
- Multiple queue strategies (simple list, per-name deque, and in-memory SQLite) that share one contract and are
  validated by shared tests.
- Strong typing and linting defaults that keep contributions consistent.

## Runtime Context and Configuration

Factory helpers resolve runtime dependencies based on `TloSettings`. Settings are loaded in three layers: explicit
keyword arguments, environment variables, and library defaults.

```python
from tlo.common import TaskRegistryEnum
from tlo.context import (
    initialize_executor,
    initialize_locker,
    initialize_queue,
    initialize_scheduler,
    initialize_settings,
    initialize_task_registry,
    initialize_task_state_store,
)

settings = initialize_settings(task_registry=TaskRegistryEnum.InMemoryTaskRegistry)
task_registry = initialize_task_registry(settings)
task_state_store = initialize_task_state_store(settings)
queue = initialize_queue(settings)
locker = initialize_locker(settings)
scheduler = initialize_scheduler(settings, registry=task_registry, queue=queue, state_store=task_state_store)
executor = initialize_executor(
    settings,
    registry=task_registry,
    queue=queue,
    scheduler=scheduler,
    state_store=task_state_store,
    locker=locker,
)

# Or build a Tlo orchestrator that wires these together for you:
# orchestrator = Tlo(tick_interval=0.1)
```

You can also point to custom implementations by providing a dotted Python path:

```python
settings = initialize_settings(task_state_store="my_app.state.RedisTaskStateStore")
```

### Exclusivity and locking

- Register exclusive tasks with a simple format string: `@registry.register(name="send_email", exclusive="{user_id}")`.
  The template is rendered with task args/kwargs to produce a lock key.
- A locker implementation (default: in-memory) guards those keys. When a lock is already held, the executor requeues the
  task with `eta = now + tick_interval` and tries again on the next tick.
- Swap lockers via `TloSettings.locker`/`TLO_LOCKER` to plug in other strategies (e.g., distributed locks) while keeping
  the same executor behaviour.

Example: task-level exclusivity (one task per user at a time)

```python
from tlo.orchestrator import Tlo

orchestrator = Tlo()

@orchestrator.register(name="send_user_digest", exclusive="{user_id}")
def send_user_digest(*, user_id: str) -> None:
    ...

# These two calls will share the same lock key "123" and run one after another
orchestrator.submit_task("send_user_digest", kwargs={"user_id": "123"})
orchestrator.submit_task("send_user_digest", kwargs={"user_id": "123"})
```

Example: whole-task exclusivity (only one instance of the task runs at a time)

```python
from tlo.orchestrator import Tlo

orchestrator = Tlo()

@orchestrator.register(name="rebuild_cache", exclusive="rebuild_cache")
def rebuild_cache() -> None:
    ...
# Any concurrent submission of "rebuild_cache" will reuse the same lock key and serialize execution.
```

Example: swapping the locker implementation

```python
from tlo.orchestrator import Tlo
from my_app.locking import RedisLocker  # your LockerProtocol implementation

orchestrator = Tlo(locker="my_app.locking.RedisLocker")
```

All locker, registry, queue, scheduler, executor, and state-store implementations can be selected via settings or `TLO_*`
environment variables (e.g., `TLO_LOCKER`, `TLO_EXECUTOR`, `TLO_QUEUE`, etc.), matching the defaults listed in
`TloSettings.from_defaults()`.

Environment variables use the `TLO_` prefix and map directly to settings fields:

| Variable               | Description                                                                | Default                  |
|------------------------|----------------------------------------------------------------------------|--------------------------|
| `TLO_TASK_REGISTRY`    | Dotted Python path or `TaskRegistryEnum` value for the task registry.      | `InMemoryTaskRegistry`   |
| `TLO_TASK_STATE_STORE` | Dotted Python path or `TaskStateStoreEnum` value for the task state store. | `InMemoryTaskStateStore` |
| `TLO_QUEUE`            | Dotted Python path or `QueueEnum` value for the queue implementation.      | `MapQueue`               |
| `TLO_TICK_INTERVAL`    | Sleep duration (seconds) between scheduler ticks.                          | `1.0`                    |
| `TLO_DEFAULT_QUEUE`    | Name of the queue used when none is provided.                              | `default`                |
| `TLO_STOP_BEHAVIOR`    | Behaviour when stopping (`Drain`, `Cancel`, or `Ignore`).                  | `Drain`                  |
| `TLO_PANIC_MODE`       | Propagate scheduler errors instead of swallowing them.                     | `False`                  |

### Configuring and overriding settings

You can override defaults via environment variables (above) or by calling `initialize_settings`/`TloSettings.load` with
keyword arguments. Keyword overrides win over env vars and defaults:

```python
settings = initialize_settings(
    queue=QueueEnum.MapQueue,
    default_queue="priority",
    tick_interval=0.25,
)
```

`TloSettings` is a plain dataclass; you can also call `settings.update(...)` before wiring components if you need to
derive values programmatically. All settings are consumed at orchestrator startup when dependencies are built; changing
the dataclass after `Tlo` (or `initialize_*`) has been called will not reconfigure already-constructed instances. To
change runtime behaviour, stop the orchestrator and recreate it with new settings.

Submitting tasks with custom routing:

```python
engine = Tlo()
engine.submit_task(
    "send_email",
    args=("user@example.com",),
    queue_name="notifications",  # use non-default queue
    eta=time.time() + 60,        # schedule for 1 minute later
)
```

### Runtime-mutability

`TloSettings` values are read when components are constructed. The orchestrator and helpers do not watch for changes to
the dataclass, so treat settings as immutable after you call `Tlo(...)` or any `initialize_*` factory. If you need to
modify configuration (e.g., switch queues, default queue name, tick interval), stop the orchestrator and build a new
instance with updated settings.

### Task State Records

`tlo.task_state_store` defines a minimal protocol and an in-memory implementation. `TaskStateRecord` captures the
lifecycle of a task execution with timestamps, result payloads, and a `TaskStatus` enum (`Pending`, `Running`, `Failed`,
`Succeeded`). Swap in your own persistence layer by registering an implementation that satisfies
`TaskStateStoreProtocol`.

## Development Workflow

Use the helper scripts in `scripts/` to keep changes validated across supported Python versions (3.10–3.14):

```bash
# Run the full test matrix (pytest across Python versions)
uv run ./scripts/test_suite.py

# Execute strict static type checks
uv run ty check .

# Lint and format the project
uv run ruff check
uv run ruff format

# Run the queue implementation parity tests
uv run pytest tests/test_queue.py
```

Docstrings use reStructuredText and are enforced by Ruff, so prefer `:param:` directives and descriptive prose when
documenting new APIs.

## Contributing

Contributions are welcome! Please open an issue or draft pull request that explains the problem you want to solve so we
can discuss the approach before merging. With the project in pre-alpha, feedback on API design and ergonomics is
especially valuable. The roadmap in `roadmap.md` outlines the next milestones if you are looking for inspiration.
