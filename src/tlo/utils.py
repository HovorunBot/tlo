"""Utility functions accessible from everywhere in the application."""

__all__ = ["make_specific_register_func", "register_implementation"]

from collections.abc import Callable

from tlo.tlo_types import TImplementation, TStrEnum


def register_implementation(
    registry: dict[TStrEnum, TImplementation], key: TStrEnum
) -> Callable[[TImplementation], TImplementation]:
    """Register a specified class into provided dictionary by specified key."""

    def wrapper(item: TImplementation) -> TImplementation:
        registry[key] = item
        return item

    return wrapper


def make_specific_register_func(
    registry_map: dict[TStrEnum, TImplementation],
) -> Callable[[TStrEnum], Callable[[TImplementation], TImplementation]]:
    """Create a specific register function for a given registry map."""

    def _register(enum_key: TStrEnum) -> Callable[[TImplementation], TImplementation]:
        return register_implementation(registry_map, enum_key)

    return _register
