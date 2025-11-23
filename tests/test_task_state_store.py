"""Tests for in-memory task state store semantics."""

from __future__ import annotations

import datetime

import pytest

from tlo.errors import TloConfigError, TloTaskStateDoesNotExistError
from tlo.task_state_store.common import TaskStateRecord, TaskStatus
from tlo.task_state_store.state_store import InMemoryTaskStateStore


def _record(id_: str = "task-1") -> TaskStateRecord:
    return TaskStateRecord(
        id=id_,
        name="task",
        created_at=datetime.datetime.now(datetime.UTC),
        created_by="test",
        status=TaskStatus.Pending,
    )


def test_create_duplicate_raises() -> None:
    """Creating a duplicate record should raise."""
    store = InMemoryTaskStateStore()
    rec = _record()
    store.create(rec)

    with pytest.raises(TloConfigError):
        store.create(_record(id_=rec.id))


def test_update_missing_raises() -> None:
    """Updating a missing record should raise."""
    store = InMemoryTaskStateStore()
    with pytest.raises(TloTaskStateDoesNotExistError):
        store.update(_record("missing"))


def test_delete_missing_raises() -> None:
    """Deleting a missing record should raise."""
    store = InMemoryTaskStateStore()
    with pytest.raises(TloTaskStateDoesNotExistError):
        store.delete("missing")
