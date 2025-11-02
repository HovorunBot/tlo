"""Public interface for the Task Layer Operations (TLO) package."""

from __future__ import annotations

from .task_registry.registry import DEFAULT_REGISTRY, TaskRegistry, register

__all__ = ["DEFAULT_REGISTRY", "TaskRegistry", "hello", "register"]


def hello() -> str:
    """Return a short greeting used by quickstart checks and smoke tests."""
    return "Hello from tlo!"
