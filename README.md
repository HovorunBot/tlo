# tlo

> **Warning:** TLO is currently in a pre-alpha stage. Breaking changes may land in any version until the first stable
> release.

TLO (Task Layer Operations) is a lightweight library for running simple background tasks without pulling in extra
dependencies.

The name comes from the Ukrainian word `тло`, which translates to "background"—a nod to the library's focus on
behind-the-scenes work.

## Development

- `uv run ./scripts/test_suite.py`  
  Spins through pytest on every supported Python version (3.10–3.14) so you can spot version-specific regressions early.
- `uv run mypy .`  
  Runs the type checker in strict mode to keep the API surface well annotated and catch potential bugs before runtime.
- `uv run ruff check`  
  Executes Ruff’s lint pass, enforcing the project’s style and safety rules in a single, fast sweep.
- `uv run ruff format`  
  Applies Ruff’s Black-compatible formatter to keep the codebase consistent without manual tweaking.
