## 🧭 TLO Development Roadmap

### 🎯 Phase 1 — Core Architecture (MVP)
Goal: Establish minimal, modular, dependency-light foundation.

**Components**
- `TaskDef` — dataclass holding callable metadata. *(Implemented in `src/tlo/task_registry/task_def.py` with automatic normalisation of integer intervals into `timedelta` values.)*
- `InMemoryTaskRegistry` — in-memory registry for task definitions. *(Shipped in `src/tlo/task_registry/registry.py`; exposes the decorator-based API now used in smoke tests.)*
- `TaskStateStore` — simple persistent store (SQLite or in-memory). *(Covered by `InMemoryTaskStateStore` in `src/tlo/task_state_store/state_store.py`; persistence backends remain future work.)*
- `Queue` — in-memory FIFO or priority queue for scheduled tasks. *(Delivered in `src/tlo/queue/queue.py` with `SimpleInMemoryQueue`, `MapQueue`, and `InMemorySqliteQueue`, all sharing `QueueProtocol` and validated by `tests/test_queue.py`.)*
- `Scheduler` — basic interval/cron-like scheduler pushing to queue. *(Pending — will be wired once queue primitives exist.)*
- `Executor` — executes callable synchronously/async. *(Pending — interface draft still outstanding.)*
- `Engine` — orchestrator; pulls from queue, delegates to executor, updates state store. *(Pending — blocked by queue/scheduler/executor foundations.)*

**Supporting infrastructure**
- `TloSettings` — runtime configuration holder. *(Available via `src/tlo/settings.py`; loads defaults, environment overrides, and supports runtime updates.)*
- `TloContext` — runtime configuration container. *(Introduced in `src/tlo/context.py`; composes the registry/state store implementations from `TloSettings` and exposes them for the Engine and other orchestrator elements.)*

**Tech constraints**
- Python ≥3.10  
- Dependencies: only `pytest`, `mypy`, `ruff`  
- All components type-hinted, lint-clean, and unit-tested.

---

### 🧩 Phase 2 — Abstractions & Extensibility
Goal: Define clear boundaries for evolution.

**Introduce interfaces**
- `AbstractTaskRegistry`
- `AbstractQueue`
- `AbstractScheduler`
- `AbstractExecutor`
- `AbstractTaskStateStore`
- *(Registry and state store abstractions now live in `src/tlo/task_registry/registry.py` and `src/tlo/task_state_store/state_store.py`. `AbstractQueue` and `QueueProtocol` ship in `src/tlo/queue/queue.py`; Scheduler/Executor interfaces remain to be defined.)*

**Keep concrete implementations**
- `InMemoryTaskRegistry`
- `InMemoryQueue`
- `SimpleScheduler`
- `LocalExecutor`
- `SqliteStateStore`

**Other refinements**
- Add `TaskId` type (UUID or namespaced str).
- Define lightweight `TaskContext` (logging, cancellation, progress).
- Engine remains single implementation using interfaces.
- *(Enums for registry and state store locations are defined in `src/tlo/common.py`. `TloContext` now represents the injected configuration for the orchestrator, while the planned `TaskContext` will focus on per-execution concerns once introduced.)*

---

### ⚙️ Phase 3 — CLI & Library Integration
Goal: Make TLO usable both as library and standalone runner.

**Tasks**
- Expose simple CLI via `click` or `argparse`:
  - `tlo run` → start engine loop  
  - `tlo schedule` → trigger scheduler  
  - `tlo list-tasks`
- Provide reusable entrypoints for embedding:
  ```python
  from tlo import Engine, DEFAULT_REGISTRY
  engine = Engine(DEFAULT_REGISTRY, ...)
  engine.run()
  ```
  
### 🌐 Phase 4 — Persistence & Observability
Goal: Add minimal reliability and visibility.

**Extensions**
- Persistent queue and state store (SQLite backend).
- Task result history with timestamps & duration.
- Simple log hooks or callback interface:
  - `on_task_started`, `on_task_failed`, etc.
- Optional in-memory metrics (executed count, avg duration).

---

### 🚀 Phase 5 — Advanced Features (Future)
Goal: Prepare for scaling and external integration.

**Planned capabilities**
- Async engine loop (anyio-based).
- Threaded / process-based executors.
- Distributed queue (Valkey/Redis backend).
- Pydantic models for external configuration and API schemas.
- REST/GraphQL/CLI inspection endpoints.
- Retry / backoff / task dependencies.
