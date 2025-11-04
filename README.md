# TLO

> **Warning:** TLO is currently in a pre-alpha stage. Public APIs and overall behaviour may change without notice until
> the first stable release.

TLO (Task Layer Operations) is a lightweight, modular toolkit for defining and running background tasks — without
committing to a full-fledged scheduler from the start. It provides a minimal registry for task definitions, strongly
typed interfaces, and pluggable state storage, enabling you to prototype background workloads quickly and evolve them
into more complex systems over time.

The name TLO comes from the Ukrainian word “тло” (tlo), meaning “background” — a nod to its focus on reliable,
behind-the-scenes task execution.

## Key Features

- Minimal, decorator-driven API for registering recurring async or sync callables.
- In-memory reference implementations (registry, queues, state store) that work immediately for prototypes and tests.
- Protocol-based registry, queue, and state-store contracts that are easy to replace with your own services.
- Multiple queue strategies (simple list, per-name deque, and in-memory SQLite) that share one contract and are
  validated by shared tests.
- Strong typing and linting defaults that keep contributions consistent.

## Runtime Context and Configuration

`TloContext` resolves runtime dependencies based on `TloSettings`. Settings are loaded in three layers: explicit keyword
arguments, environment variables, and library defaults.

```python
from tlo.common import TaskRegistryEnum
from tlo.context import TloContext

context = TloContext(task_registry=TaskRegistryEnum.InMemoryTaskRegistry)

task_registry = context._task_registry
task_state_store = context._task_state_store
```

You can also point to custom implementations by providing a dotted Python path:

```python
context = TloContext(task_state_store="my_app.state.RedisTaskStateStore")
```

Environment variables use the `TLO_` prefix and map directly to settings fields:

| Variable               | Description                                                                | Default                  |
|------------------------|----------------------------------------------------------------------------|--------------------------|
| `TLO_TASK_REGISTRY`    | Dotted Python path or `TaskRegistryEnum` value for the task registry.      | `InMemoryTaskRegistry`   |
| `TLO_TASK_STATE_STORE` | Dotted Python path or `TaskStateStoreEnum` value for the task state store. | `InMemoryTaskStateStore` |
| `TLO_QUEUE`            | Dotted Python path or `QueueEnum` value for the queue implementation.      | `MapQueue`               |

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
uv run mypy .

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
