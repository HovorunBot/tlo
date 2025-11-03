"""Public interface for the Task Layer Operations (TLO) package."""

from __future__ import annotations

from .task_registry.registry import InMemoryTaskRegistry

__all__ = ["InMemoryTaskRegistry", "hello"]


def hello() -> str:
    """Return a short greeting used by quickstart checks and smoke tests."""
    return "Hello from tlo!"
