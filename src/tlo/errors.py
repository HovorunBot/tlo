"""Module containing TLO-related errors."""


class TloError(Exception):
    """Base class for all TLO-related errors."""


class TaskIsNotRegisteredError(TloError):
    """Raised when you try to get a task which is not registered."""
