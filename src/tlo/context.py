"""Initialize runtime services defined by :class:`~tlo.settings.TloSettings`."""

from enum import StrEnum
import importlib
from typing import Any, Unpack, assert_never

from tlo.common import (
    ExecutorEnum,
    LockerEnum,
    QueueEnum,
    SchedulerEnum,
    TaskRegistryEnum,
    TaskStateStoreEnum,
)
from tlo.errors import TloConfigError
from tlo.executor.executor import KNOWN_EXECUTORS, ExecutorProtocol
from tlo.locking.locker import KNOWN_LOCKERS, LockerProtocol
from tlo.queue.queue import KNOWN_QUEUES, QueueProtocol
from tlo.scheduler.scheduler import KNOWN_SCHEDULERS, SchedulerProtocol
from tlo.settings import Loader, TloSettings, TloSettingsKwargs
from tlo.task_registry.registry import (
    KNOWN_TASK_REGISTRIES,
    TaskRegistryProtocol,
)
from tlo.task_state_store.state_store import (
    KNOWN_TASK_STATE_STORES,
    TaskStateStoreProtocol,
)


def initialize_settings(**settings: Unpack[TloSettingsKwargs]) -> TloSettings:
    """Initialize `TloSettings` using the Loader.

    Note: No root prefix is applied here; environment variables will be read
    without a prefix unless the caller performs loading elsewhere with a
    specific `root_prefix`.
    """
    return Loader().load(TloSettings, overrides=dict(settings))


def initialize_task_registry(settings: TloSettings) -> TaskRegistryProtocol:
    """Build the task registry declared in settings."""
    return _initialize(
        settings.task_registry,
        KNOWN_TASK_REGISTRIES,
        TaskRegistryProtocol,  # type: ignore[type-abstract]
        TaskRegistryEnum,
    )


def initialize_task_state_store(settings: TloSettings) -> TaskStateStoreProtocol:
    """Build the task state store declared in settings."""
    return _initialize(
        settings.task_state_store,
        KNOWN_TASK_STATE_STORES,
        TaskStateStoreProtocol,  # type: ignore[type-abstract]
        TaskStateStoreEnum,
    )


def initialize_queue(settings: TloSettings) -> QueueProtocol:
    """Build the queue declared in settings."""
    return _initialize(
        settings.queue,
        KNOWN_QUEUES,
        QueueProtocol,  # type: ignore[type-abstract]
        QueueEnum,
        settings=settings,
    )


def initialize_scheduler(
    settings: TloSettings,
    *,
    registry: TaskRegistryProtocol,
    queue: QueueProtocol,
    state_store: TaskStateStoreProtocol,
) -> SchedulerProtocol:
    """Build the scheduler declared in settings."""
    return _initialize(
        settings.scheduler,
        KNOWN_SCHEDULERS,
        SchedulerProtocol,  # type: ignore[type-abstract]
        SchedulerEnum,
        registry=registry,
        queue=queue,
        state_store=state_store,
        settings=settings,
    )


def initialize_executor[
    TRegistry: TaskRegistryProtocol,
    TStateStore: TaskStateStoreProtocol,
    TQueue: QueueProtocol,
    TScheduler: SchedulerProtocol,
](
    settings: TloSettings,
    *,
    registry: TRegistry,
    state_store: TStateStore,
    queue: TQueue,
    scheduler: TScheduler,
    locker: LockerProtocol,
) -> ExecutorProtocol:
    """Build the executor declared in settings."""
    return _initialize(
        settings.executor,
        KNOWN_EXECUTORS,
        ExecutorProtocol,  # type: ignore[type-abstract]
        ExecutorEnum,
        registry=registry,
        state_store=state_store,
        queue=queue,
        scheduler=scheduler,
        locker=locker,
        settings=settings,
    )


def initialize_locker(settings: TloSettings) -> LockerProtocol:
    """Build the locker declared in settings."""
    return _initialize(
        settings.locker,
        KNOWN_LOCKERS,
        LockerProtocol,  # type: ignore[type-abstract]
        LockerEnum,
    )


def _unregistered_known_type[TStrEnum: StrEnum](type_: TStrEnum) -> AssertionError:
    """Return an error when a known enum value lacks a registered implementation."""
    msg = (
        f"Found unregistered type: {type_!r}. "
        f"If you are developer, ensure you register it here. "
        f"If you are library user, please issue the error to development team."
    )
    return AssertionError(msg)


def _invalid_specified_type[TImplementation](py_path: str, expected_type: type[TImplementation]) -> TloConfigError:
    """Return an error when importing a dotted path yields the wrong type."""
    msg = (
        f"Object specified by {py_path!r} is not an instance of {expected_type!r}. "
        f"Please, ensure correctness of application configuration."
    )
    return TloConfigError(msg)


def _initialize[TStrEnum: StrEnum, TImplementation](
    settings_value: TStrEnum | str,
    impl_registry: dict[TStrEnum, type[TImplementation]],
    expected_type: type[TImplementation],
    enum_type: type[TStrEnum],
    **kwargs: Any,
) -> TImplementation:
    """Instantiate either a registered enum implementation or a dotted Python path.

    :param settings_value: Value provided by :class:`TloSettings`, either an enum member
        or a dotted import path string.
    :param impl_registry: Mapping of enum values to concrete classes.
    :param expected_type: Protocol or abstract base class that the result must satisfy.
    :param enum_type: Enum class associated with *impl_registry*.
    :param kwargs: Arguments passed to the constructor.
    :returns: Instantiated implementation matching *settings_value*.
    :raises AssertionError: If an enum value is not registered.
    :raises TloConfigError: If the dotted path resolves to an incompatible type.
    """
    match settings_value:
        case _ if isinstance(settings_value, enum_type):
            if settings_value in impl_registry:
                return impl_registry[settings_value](**kwargs)
            raise _unregistered_known_type(settings_value)
        case str():
            return _initialize_by_py_path(settings_value, expected_type, **kwargs)
        case _:
            raise assert_never(settings_value)


def _initialize_by_py_path[TImplementation](
    py_path: str, expected_type: type[TImplementation], **kwargs: Any
) -> TImplementation:
    """Resolve a dotted Python path into an instantiated object.

    :param py_path: Fully qualified import path in the ``package.module.Class`` format.
    :param expected_type: Protocol or ABC instance the resulting object must satisfy.
    :param kwargs: Arguments passed to the constructor.
    :returns: An instance of the class referred to by *py_path*.
    :raises ImportError: If the module portion cannot be imported.
    :raises AttributeError: If the target attribute is missing.
    :raises TloConfigError: If the object does not implement *expected_type*.
    """
    module, klass = py_path.rsplit(".", 1)
    module_obj = importlib.import_module(module)
    result = getattr(module_obj, klass)(**kwargs)
    if not isinstance(result, expected_type):
        raise _invalid_specified_type(py_path, expected_type)
    return result
