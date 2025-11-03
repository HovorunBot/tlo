"""Some common constants and objects which may be used in any modules."""

from __future__ import annotations

from tlo.py_compatibility import StrEnum


class TaskRegistryEnum(StrEnum):
    """Enum of known task registries."""

    InMemoryTaskRegistry = "InMemoryTaskRegistry"


class TaskStateStoreEnum(StrEnum):
    """Enum of known task state stores."""

    InMemoryTaskStateStore = "InMemoryTaskStateStore"
