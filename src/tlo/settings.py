"""Settings for the TLO runtime and useful functionality to work with them."""

from __future__ import annotations

import dataclasses
import os
from typing import Any, NotRequired, TypedDict, Unpack

from tlo.common import (
    ExecutorEnum,
    QueueEnum,
    SchedulerEnum,
    StopBehaviorEnum,
    TaskRegistryEnum,
    TaskStateStoreEnum,
)
from tlo.errors import TloConfigError
from tlo.executor.executor import LocalExecutor


class TloSettingsKwargs(TypedDict):
    """Kwargs accepted by :meth:`TloSettings.load`."""

    task_registry: NotRequired[TaskRegistryEnum | str]
    task_state_store: NotRequired[TaskStateStoreEnum | str]
    queue: NotRequired[QueueEnum | str]
    scheduler: NotRequired[SchedulerEnum | str]
    executor: NotRequired[ExecutorEnum | str]
    tick_interval: NotRequired[float]
    default_queue: NotRequired[str]
    stop_behavior: NotRequired[StopBehaviorEnum]
    panic_mode: NotRequired[bool]


@dataclasses.dataclass
class TloSettings:
    """Strongly typed configuration holder for TLO runtime services."""

    task_registry: TaskRegistryEnum | str
    task_state_store: TaskStateStoreEnum | str
    queue: QueueEnum | str
    scheduler: SchedulerEnum | str
    executor: ExecutorEnum | str
    tick_interval: float
    default_queue: str
    stop_behavior: StopBehaviorEnum
    panic_mode: bool

    @classmethod
    def from_defaults(cls) -> dict[str, Any]:
        """Return the canonical default values for all settings fields."""
        return {
            "task_registry": TaskRegistryEnum.InMemoryTaskRegistry,
            "task_state_store": TaskStateStoreEnum.InMemoryTaskStateStore,
            "queue": QueueEnum.MapQueue,
            "scheduler": SchedulerEnum.SimpleScheduler,
            "executor": LocalExecutor.get_name(),
            "tick_interval": 1.0,
            "default_queue": "default",
            "stop_behavior": StopBehaviorEnum.Drain,
            "panic_mode": False,
        }

    @classmethod
    def load(cls, **settings: Any) -> TloSettings:
        """Load settings from keyword overrides, env vars, and defaults (in that order).

        :param settings: Keyword arguments that override both environment variables and defaults.
        :returns: A fully instantiated :class:`TloSettings` object.
        """
        final_settings = cls.from_defaults()
        final_settings.update(cls.from_envs())
        final_settings.update(settings)
        return cls(**final_settings)

    def update(self, **settings: Unpack[TloSettingsKwargs]) -> None:
        """Apply keyword overrides directly to the instance."""
        for k, v in settings.items():
            if hasattr(self, k):
                setattr(self, k, v)

    def as_dict(self) -> dict[str, Any]:
        """Return specified settings as a plain dictionary for serialisation."""
        return dataclasses.asdict(self)

    @classmethod
    def from_envs(cls) -> dict[str, Any]:
        """Return settings overridden via ``TLO_*`` environment variables."""
        coercers: dict[str, Any] = {
            "task_registry": lambda v: _enum_or_path(v, TaskRegistryEnum),
            "task_state_store": lambda v: _enum_or_path(v, TaskStateStoreEnum),
            "queue": lambda v: _enum_or_path(v, QueueEnum),
            "scheduler": lambda v: _enum_or_path(v, SchedulerEnum),
            "executor": lambda v: _enum_or_path(v, ExecutorEnum),
            "tick_interval": _to_float,
            "stop_behavior": lambda v: StopBehaviorEnum(v),
            "panic_mode": _to_bool,
        }

        to_return: dict[str, Any] = {}
        for field in dataclasses.fields(cls):
            env_var = f"TLO_{field.name.upper()}"
            if env_var not in os.environ:
                continue
            raw_value = os.environ[env_var]
            if field.name not in coercers:
                to_return[field.name] = raw_value
                continue

            try:
                to_return[field.name] = coercers[field.name](raw_value)
            except ValueError as exc:
                msg = f"{raw_value!r} is not a valid value for {field.name!r}"
                raise TloConfigError(msg) from exc
        return to_return


def _enum_or_path(value: str, enum_cls: Any) -> Any:
    try:
        return enum_cls(value)
    except ValueError:
        return value


def _to_float(value: str) -> float:
    return float(value)


def _to_bool(value: str) -> bool:
    truthy = {"1", "true", "yes", "on"}
    falsy = {"0", "false", "no", "off"}
    lower = value.lower()
    if lower in truthy:
        return True
    if lower in falsy:
        return False
    msg = f"Must be a boolean (one of {sorted(truthy | falsy)}), got {value!r}"
    raise ValueError(msg)
