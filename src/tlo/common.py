"""Some common constants and objects which may be used in any modules."""

from __future__ import annotations

from abc import ABC, abstractmethod
from functools import cached_property
import sqlite3
from typing import Final

from tlo.py_compatibility import StrEnum

TLO_DEFAULT_QUEUE_NAME: Final[str] = "default"


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
    InMemorySqliteQueue = "InMemorySqliteQueue"


class WithSqliteInMemory(ABC):
    """Mixin providing access to SQLite in-memory database for storing data."""

    @cached_property
    def sqlite_connection(self) -> sqlite3.Connection:
        """Return a connection to the in-memory SQLite database."""
        connection = sqlite3.connect(
            "file::memory:?cache=shared", uri=True, check_same_thread=False
        )
        cursor = connection.cursor()
        cursor.execute("PRAGMA journal_mode=OFF;")  # no journaling needed
        cursor.execute("PRAGMA synchronous=OFF;")  # skip fsync safety (safe in RAM)
        cursor.execute("PRAGMA temp_store=MEMORY;")  # temp tables also in RAM
        cursor.execute("PRAGMA locking_mode=EXCLUSIVE;")  # avoid file locks
        cursor.execute("PRAGMA cache_size=-10000;")  # 10 MB cache (negative = KB units)
        cursor.close()
        return connection

    @abstractmethod
    def _init_schema(self) -> None:
        """Initialize the schema in the in-memory SQLite database for a required data object."""
