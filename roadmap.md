## 🧭 TLO Development Roadmap

### 🎯 Phase 1 — Core Architecture (MVP) ✅
Goal: Minimal, modular, dependency-light foundation using in-memory defaults and factory helpers.

**Components (implemented)**
- `TaskDef` with interval/cron scheduling helpers (`src/tlo/task_registry/task_def.py`).
- `InMemoryTaskRegistry` with decorator API (`src/tlo/task_registry/registry.py`).
- `InMemoryTaskStateStore` (`src/tlo/task_state_store/state_store.py`).
- Queues: `SimpleInMemoryQueue`, `MapQueue`, plus admin hooks (move/reschedule/bulk peek) in `src/tlo/queue/queue.py`.
- `SimpleScheduler` for interval/cron ticking (`src/tlo/scheduler/scheduler.py`).
- `LocalExecutor` (synchronous, round-robin across queues) (`src/tlo/executor/executor.py`).
- `Tlo` orchestrator with queue routing/peek/admin proxies (`src/tlo/orchestrator/orchestrator.py`).

**Supporting infrastructure**
- `TloSettings` (env/kwarg/default merge, typed overrides including `default_queue`) in `src/tlo/settings.py`.
- Initializer helpers (`initialize_*`) in `src/tlo/context.py` to build registry/state store/queue/scheduler/executor from settings.

**Tech constraints**
- Python ≥3.12; deps: `pytest`, `mypy`, `ruff`; code is typed, linted, and tested.

---

### 🧩 Phase 2 — Abstractions & Extensibility ✅
Goal: Define clear boundaries for evolution. Core protocols/ABCs are present; per-task context remains intentionally out
of scope for the synchronous LocalExecutor (cancellation is unsupported beyond TypeError signalling).

**Introduce interfaces**
- `AbstractTaskRegistry`
- `AbstractQueue`
- `AbstractScheduler`
- `AbstractExecutor`
- `AbstractTaskStateStore`
- *(All abstractions now ship: registries/state stores in `src/tlo/task_registry/registry.py` and `src/tlo/task_state_store/state_store.py`; queues in `src/tlo/queue/queue.py`; scheduler and executor protocols in their respective modules.)*

**Concrete implementations in tree**
- `InMemoryTaskRegistry`
- `MapQueue` / `SimpleInMemoryQueue`
- `SimpleScheduler`
- `LocalExecutor`
- `InMemoryTaskStateStore`

**Other refinements**
- `TaskId` alias exists in `tlo_types`.
- Executor interface exposes `stop_task` (returns final state; raises TypeError for non-interruptible executors) and
  `get_task_state` for inspection; LocalExecutor explicitly cannot stop running tasks.
- Engine remains single implementation using interfaces.
- Enforce import hygiene and typed settings surface.

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
  from tlo import Tlo
  engine = Tlo()
  engine.run()
  ```
  
### 🌐 Phase 4 — Persistence & Observability
Goal: Add minimal reliability and visibility.

**Extensions**
- Persistent queue and state store (SQLite backend).
- Task result history with timestamps & duration.
- Simple log hooks or callback interface:
  - `on_task_started`, `on_task_failed`, etc. *(open: lifecycle/telemetry protocol)*
- Task state store queries (filter/list/search) for inspection UIs. *(open)*
- Exclusive task execution contract (registration flag + executor enforcement). *(open)*
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
