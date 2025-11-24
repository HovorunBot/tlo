"""Some common constants and objects which may be used in any modules."""

from __future__ import annotations

__all__ = [
    "ExecutorEnum",
    "LockerEnum",
    "QueueEnum",
    "SchedulerEnum",
    "StopBehaviorEnum",
    "TaskRegistryEnum",
    "TaskStateStoreEnum",
]

from enum import StrEnum


class TaskRegistryEnum(StrEnum):
    """Enum of known task registries."""

    InMemoryTaskRegistry = "InMemoryTaskRegistry"


class TaskStateStoreEnum(StrEnum):
    """Enum of known task state stores."""

    InMemoryTaskStateStore = "InMemoryTaskStateStore"


class QueueEnum(StrEnum):
    """Enum of known queues."""

    SimpleInMemoryQueue = "SimpleInMemoryQueue"
    MapQueue = "MapQueue"


class SchedulerEnum(StrEnum):
    """Enum of known schedulers."""

    SimpleScheduler = "SimpleScheduler"


class ExecutorEnum(StrEnum):
    """Enum of known executors."""

    LocalExecutor = "LocalExecutor"


class LockerEnum(StrEnum):
    """Enum of known lockers."""

    InMemoryLocker = "InMemoryLocker"


class StopBehaviorEnum(StrEnum):
    """Enum describing what to do with queued tasks when stopping."""

    Drain = "Drain"
    Cancel = "Cancel"
    Ignore = "Ignore"
