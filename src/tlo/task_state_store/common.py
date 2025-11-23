"""Contains common objects and functionality for task state store."""

import dataclasses
from datetime import datetime
from enum import StrEnum
from typing import Any

from tlo.tlo_types import FuncName, TaskId


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
    Cancelled = "Cancelled"
    """Task was cancelled."""


@dataclasses.dataclass(slots=True)
class TaskStateRecord:
    """Describe a record of a task execution result."""

    id: TaskId
    name: FuncName
    created_at: datetime
    created_by: str
    started_at: datetime | None = None
    finished_at: datetime | None = None
    status: TaskStatus = TaskStatus.Pending
    result: Any | None = None
