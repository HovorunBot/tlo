"""Settings for the TLO runtime and useful functionality to work with them."""

from __future__ import annotations

import dataclasses
import os
from typing import Any

from tlo.common import QueueEnum, TaskRegistryEnum, TaskStateStoreEnum


@dataclasses.dataclass
class TloSettings:
    """Settings for the TLO runtime."""

    task_registry: TaskRegistryEnum | str
    task_state_store: TaskStateStoreEnum | str
    queue: QueueEnum | str

    @classmethod
    def from_defaults(cls) -> dict[str, Any]:
        """Return default settings of the TLO runtime."""
        return {
            "task_registry": TaskRegistryEnum.InMemoryTaskRegistry,
            "task_state_store": TaskStateStoreEnum.InMemoryTaskStateStore,
            "queue": QueueEnum.MapQueue,
        }

    @classmethod
    def from_envs(cls) -> dict[str, Any]:
        """Return settings specified as environment variables."""
        to_return = {}
        for field in dataclasses.fields(cls):
            env_var = f"TLO_{field.name.upper()}"
            if env_var in os.environ:
                to_return[field.name] = os.environ[env_var]
        return to_return

    @classmethod
    def load(cls, **settings: Any) -> TloSettings:
        """Load settings from different sources in order of precedence.

        1. directly specified settings;
        2. settings from environment variables;
        3. default settings;

        :param settings: Settings to override defaults and environment variables.
        :return: The loaded settings.
        """
        final_settings = cls.from_defaults()
        final_settings.update(cls.from_envs())
        final_settings.update(settings)
        return cls(**final_settings)

    def update(self, **settings: Any) -> None:
        """Allow modifying values at runtime."""
        for k, v in settings.items():
            if hasattr(self, k):
                setattr(self, k, v)

    def as_dict(self) -> dict[str, Any]:
        """Return specified settings as a dictionary."""
        return dataclasses.asdict(self)
