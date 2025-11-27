"""Utility coercers used by settings loading.

This module intentionally has no external dependencies and provides a few
lightweight helpers that can be referenced from settings field metadata
(``env_coercer``). They convert environment variable strings into desired
Python types without pulling in extra packages.

The functions here are pure and raise only standard exceptions where noted so
that the settings loader can wrap errors into :class:`tlo.errors.TloConfigError`.
"""

from enum import StrEnum


def identity[T](x: T) -> T:
    """Return the input value unchanged.

    :param x: Any value.
    :returns: The same value ``x``.
    """
    return x


def enum_or_original[TStrEnum: StrEnum](value: str, enum_cls: type[TStrEnum]) -> TStrEnum | str:
    """Coerce a string into a :class:`~enum.StrEnum` member or return the original.

    :param value: The string to coerce.
    :param enum_cls: A subclass of :class:`~enum.StrEnum` to try converting into.
    :returns: The matching enum member if conversion succeeds, otherwise ``value``.
    """
    try:
        return enum_cls(value)
    except ValueError:
        return value


def to_bool(value: str) -> bool:
    """Convert a string into a boolean in a user-friendly, case-insensitive way.

    :param value: The string value to interpret.
    :returns: ``True`` or ``False`` based on the accepted sets.
    :raises ValueError: If ``value`` is not in any accepted set.
    """
    truthy = {"1", "true", "yes", "on"}
    falsy = {"0", "false", "no", "off"}
    lower = value.lower()
    if lower in truthy:
        return True
    if lower in falsy:
        return False
    msg = f"Must be a boolean (one of {sorted(truthy | falsy)}), got {value!r}"
    raise ValueError(msg)
