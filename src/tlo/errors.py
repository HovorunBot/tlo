"""Module containing TLO-related errors."""


class TloError(Exception):
    """Base class for all TLO-related errors."""


class TaskIsNotRegisteredError(TloError, KeyError):
    """Raised when you try to get a task which is not registered."""


class TloApplicationError(TloError, AssertionError):
    """Raised when a TLO development error occurred.

    Used for future-proofing of some functions to ensure code is working as expected during the development phase.
    """


class InvalidSpecifiedTypeError(TloError, TypeError):
    """Raised when a specified type by settings is invalid."""
