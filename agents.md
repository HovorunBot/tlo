# Agent Playbook

Guidelines for LLM coding assistants working on this repo. Human-facing guidance lives in `README.md`.

## Scope and defaults

- Target Python 3.12; do not lower or widen the supported range without explicit user direction.
- Breaking changes to alpha APIs are acceptable, but avoid breaking existing configuration knobs or defaults unless the
  feature has been explicitly removed.
- Assume prior configuration should keep working (env vars, enums, dotted-path overrides) after changes.

## Application goals

- Provide a lightweight, modular background task runner with swappable registry, queue, scheduler, executor, and state
  store implementations.
- Keep in-memory defaults working out of the box while allowing dotted-path overrides for custom implementations.
- Maintain strong typing (protocols/ABCs), reST docstrings, and minimal dependencies; keep configuration via `TLO_*`
  env vars intact.

## Making changes

- Keep to existing interfaces when fixing issues; do not refactor public protocols/ABCs/enums unless the user explicitly
  asks for new code/behaviour.
- Add new dependencies only after explicit user confirmation.
- Follow the existing style: reST docstrings, Ruff formatting, 120-char lines, minimal comments, and the current
  package/module layout.
- Prefer adding functionality only when the user explicitly requests it.

## Feature and testing approach

- Use mast follow Test Driven Development approach for new features: agree requirements first, ask for clarifications
  until confident, then write tests before code.
- Avoid mocks unless explicitly requested when isolating third-party APIs or when faking environment variables.
- Apply standard PEP-8 naming (snake_case for members, PascalCase for classes/enums, UPPER_SNAKE_CASE for constants).
- Tests live in `tests/` (separate from `src/`) in `test_*.py` files with `test_*` functions; keep fixtures/helpers
  scoped to tests.
- Keep parent/child naming aligned for related types (e.g., `QueueProtocol` → `AbstractQueue` → `MapQueue`).

## Validation (run unless the user says otherwise)

- `uv run ruff format`
- `uv run ruff check`
- `uv run ty check .`
- `uv run ./scripts/test_suite.py`
- If a required command cannot be run, explain why and what coverage is missing.

## Safety and hygiene

- Do not revert user changes or edit built artifacts (e.g., `dist/`) unless asked.
- Preserve default queue/scheduler/executor/task registry/state store wiring and env var behaviour unless intentionally
  changing it with user approval.
