"""Create and configure the :class:`~tlo.context.TloContext` runtime container."""

import importlib
from typing import Any, cast

from typing_extensions import assert_never

from tlo.common import QueueEnum, TaskRegistryEnum, TaskStateStoreEnum
from tlo.errors import InvalidSpecifiedTypeError, TloApplicationError
from tlo.queue.queue import KNOWN_QUEUES, QueueProtocol
from tlo.settings import TloSettings
from tlo.task_registry.registry import (
    KNOWN_TASK_REGISTRIES,
    TaskRegistryProtocol,
)
from tlo.task_state_store.state_store import (
    KNOWN_TASK_STATE_STORES,
    TaskStateStoreProtocol,
)
from tlo.tlo_types import TImplementation, TStrEnum


class TloContext:
    """Container responsible for building registries defined in the settings.

    The context isolates the logic that resolves user configuration into concrete runtime
    services so the rest of the application can depend on a single entrypoint.
    """

    def __init__(self, **settings: Any) -> None:
        """Initialise the context with the registries selected in :class:`~tlo.settings.TloSettings`."""
        self._settings = TloSettings.load(**settings)
        self._task_registry = self._initialize(
            self._settings.task_registry,
            KNOWN_TASK_REGISTRIES,
            TaskRegistryProtocol,  # type: ignore[type-abstract]
            TaskRegistryEnum,
        )
        self._task_state_store = self._initialize(
            self._settings.task_state_store,
            KNOWN_TASK_STATE_STORES,
            TaskStateStoreProtocol,  # type: ignore[type-abstract]
            TaskStateStoreEnum,
        )
        self._queue = self._initialize(
            self._settings.queue,
            KNOWN_QUEUES,
            QueueProtocol,  # type: ignore[type-abstract]
            QueueEnum,
        )

    def _unregistered_known_type(self, type_: TStrEnum) -> TloApplicationError:
        msg = (
            f"Found unregistered type: {type_!r}. "
            f"If you are developer, ensure you register it here. "
            f"If you are library user, please issue the error to development team."
        )
        return TloApplicationError(msg)

    def _invalid_specified_type(
        self, py_path: str, expected_type: type[TImplementation]
    ) -> InvalidSpecifiedTypeError:
        msg = (
            f"Object specified by {py_path!r} is not an instance of {expected_type!r}. "
            f"Please, ensure correctness of application configuration."
        )
        return InvalidSpecifiedTypeError(msg)

    # TODO: as we drop support for Python 3.10 and 3.11, we can implement this function as generic
    # with new generic syntax
    def _initialize(
        self,
        settings_value: TStrEnum | str,
        registry: dict[TStrEnum, type[TImplementation]],
        expected_type: type[TImplementation],
        enum_type: type[TStrEnum],
    ) -> TImplementation:
        match settings_value:
            case _ if isinstance(settings_value, enum_type):
                if settings_value in registry:
                    return registry[settings_value]()
                raise self._unregistered_known_type(settings_value)
            case str():
                return self._initialize_by_py_path(settings_value, expected_type)
            case _:
                raise assert_never(settings_value)

    def _initialize_by_py_path(
        self, py_path: str, expected_type: type[TImplementation]
    ) -> TImplementation:
        """Resolve a dotted Python path into an instantiated object.

        :param py_path: Fully qualified import path in the ``package.module.Class`` format.
        :returns: An instance of the class referred to by *py_path*.
        :raises (ImportError, AttributeError): If the path cannot be imported.
        """
        module, klass = py_path.rsplit(".", 1)
        module_obj = importlib.import_module(module)
        result = cast("TImplementation", getattr(module_obj, klass)())
        if not isinstance(result, expected_type):
            raise self._invalid_specified_type(py_path, expected_type)
        return cast("TImplementation", getattr(module_obj, klass)())
