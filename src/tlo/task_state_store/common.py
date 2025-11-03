"""Contains common objects and functionality for task state store."""

import dataclasses
from datetime import datetime
from typing import Any

from tlo.py_compatibility import StrEnum


class TaskStatus(StrEnum):
    """Enum of task statuses."""

    Pending = "Pending"
    """Task is waiting for execution."""
    Running = "Running"
    """Task is currently executing."""
    Failed = "Failed"
    """Task failed to execute."""
    Succeeded = "Succeeded"
    """Task executed successfully."""


@dataclasses.dataclass(slots=True, frozen=True)
class TaskStateRecord:
    """Describe a record of a task execution result."""

    id: str
    name: str
    created_at: datetime
    started_at: datetime | None = None
    finished_at: datetime | None = None
    status: TaskStatus = TaskStatus.Pending
    result: Any | None = None
    failed: bool = False
