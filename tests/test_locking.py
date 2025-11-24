"""Tests for locker context manager behaviour."""

from __future__ import annotations

import pytest

from tlo.locking import InMemoryLocker


def test_guard_releases_lock_on_exit() -> None:
    """Guard should acquire and release locks automatically."""
    locker = InMemoryLocker()

    with locker.guard("a") as acquired:
        assert acquired
        assert locker.is_locked("a")

    assert not locker.is_locked("a")


def test_guard_releases_on_exception() -> None:
    """Guard should release locks even when exceptions are raised."""
    locker = InMemoryLocker()

    def _raise() -> None:
        with locker.guard("b") as acquired:
            assert acquired
            msg = "boom"
            raise RuntimeError(msg)

    with pytest.raises(RuntimeError):
        _raise()

    assert not locker.is_locked("b")


def test_guard_false_when_already_locked() -> None:
    """Guard should return False without releasing pre-held locks."""
    locker = InMemoryLocker()
    assert locker.acquire("c")

    with locker.guard("c") as acquired:
        assert acquired is False
        assert locker.is_locked("c")

    assert locker.is_locked("c")
