"""Module containing TLO-related errors."""


class TloError(Exception):
    """Base class for all TLO-related errors."""


class TloConfigError(TloError):
    """Raised when configuration or settings values are invalid."""


class TloInputError(TloError):
    """Raised when an input value is invalid."""


class TloTaskLookupError(TloError):
    """Raised when you try to get a task which is not registered."""


class TloInvalidRegistrationError(TloError):
    """Raised when you incorrectly register a task."""


class TloQueueEmptyError(TloError):
    """Raised when attempting to dequeue or remove from an empty queue."""


class TloTaskStateDoesNotExistError(TloError):
    """Raised when attempting to retrieve a task state that does not exist."""


class TloTaskAlreadyFinishedError(TloError):
    """Raised when attempting to stop or modify a task that has already finished."""
