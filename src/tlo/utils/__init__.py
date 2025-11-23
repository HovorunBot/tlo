"""Utility functions accessible from everywhere in the application."""

__all__ = ["make_specific_register_func", "register_implementation"]

from collections.abc import Callable
from enum import StrEnum


def register_implementation[TStrEnum: StrEnum, TImplementation](
    registry: dict[TStrEnum, TImplementation], key: TStrEnum
) -> Callable[[TImplementation], TImplementation]:
    """Return a decorator that registers a class under *key* inside *registry*."""

    def wrapper(item: TImplementation) -> TImplementation:
        registry[key] = item
        return item

    return wrapper


def make_specific_register_func[TStrEnum: StrEnum, TImplementation](
    registry_map: dict[TStrEnum, TImplementation],
) -> Callable[[TStrEnum], Callable[[TImplementation], TImplementation]]:
    """Build a helper that mirrors :func:`register_implementation` for a given map."""

    def _register(enum_key: TStrEnum) -> Callable[[TImplementation], TImplementation]:
        return register_implementation(registry_map, enum_key)

    return _register
