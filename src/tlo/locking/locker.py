"""Locker abstractions to coordinate exclusive task execution."""

from __future__ import annotations

from abc import ABC, abstractmethod
from contextlib import AbstractContextManager, contextmanager
from threading import Lock
from typing import TYPE_CHECKING, Protocol, runtime_checkable

from tlo.common import LockerEnum
from tlo.utils import make_specific_register_func

if TYPE_CHECKING:
    from collections.abc import Iterator

KNOWN_LOCKERS: dict[LockerEnum, type[LockerProtocol]] = {}
_register = make_specific_register_func(KNOWN_LOCKERS)


@runtime_checkable
class LockerProtocol(Protocol):
    """Protocol for locker implementations used to guard exclusive tasks."""

    def acquire(self, key: str) -> bool:
        """Acquire a lock for *key*.

        :returns: ``True`` if lock was acquired, ``False`` otherwise.
        """

    def release(self, key: str) -> None:
        """Release a lock for *key*."""

    def is_locked(self, key: str) -> bool:
        """Return ``True`` if *key* is currently locked."""

    def guard(self, key: str) -> AbstractContextManager[bool]:
        """Return a context manager that acquires/release a lock for *key*."""


class AbstractLocker(LockerProtocol, ABC):
    """Base locker class."""

    @abstractmethod
    def acquire(self, key: str) -> bool:
        """Acquire a lock for *key*."""

    @abstractmethod
    def release(self, key: str) -> None:
        """Release a lock for *key*."""

    @abstractmethod
    def is_locked(self, key: str) -> bool:
        """Return ``True`` if *key* is currently locked."""

    def guard(self, key: str) -> AbstractContextManager[bool]:
        """Return a context manager that acquires and releases *key*."""

        @contextmanager
        def _guard() -> Iterator[bool]:
            acquired = self.acquire(key)
            try:
                yield acquired
            finally:
                if acquired:
                    self.release(key)

        return _guard()


@_register(LockerEnum.InMemoryLocker)
class InMemoryLocker(AbstractLocker):
    """In-memory locker suitable for single-process execution."""

    def __init__(self) -> None:
        """Initialise internal lock tracking."""
        self._lock = Lock()
        self._keys: set[str] = set()

    def acquire(self, key: str) -> bool:
        """Acquire a lock for *key* if available."""
        with self._lock:
            if key in self._keys:
                return False
            self._keys.add(key)
            return True

    def release(self, key: str) -> None:
        """Release lock for *key* if held."""
        with self._lock:
            self._keys.discard(key)

    def is_locked(self, key: str) -> bool:
        """Return True when *key* is locked."""
        with self._lock:
            return key in self._keys
