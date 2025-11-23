"""Tests for duplicate task registration handling."""

from __future__ import annotations

import re

import pytest

from tlo.errors import TloInvalidRegistrationError
from tlo.task_registry.registry import InMemoryTaskRegistry


def test_duplicate_registration_raises() -> None:
    """Duplicate registrations should raise with a clear message."""
    registry = InMemoryTaskRegistry()

    @registry.register()
    def task() -> None:
        return None

    with pytest.raises(
        TloInvalidRegistrationError,
        match=re.escape(
            "Task 'task' is already registered. Use a unique name or avoid duplicate decorators."
        ),
    ):

        @registry.register(name="task")
        def task_again() -> None:
            return None
