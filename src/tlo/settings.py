"""Settings for the TLO runtime and useful functionality to work with them."""

from __future__ import annotations

import dataclasses
import os
from typing import Any

from tlo.common import QueueEnum, TaskRegistryEnum, TaskStateStoreEnum


@dataclasses.dataclass
class TloSettings:
    """Strongly typed configuration holder for TLO runtime services."""

    task_registry: TaskRegistryEnum | str
    task_state_store: TaskStateStoreEnum | str
    queue: QueueEnum | str

    @classmethod
    def from_defaults(cls) -> dict[str, Any]:
        """Return the canonical default values for all settings fields."""
        return {
            "task_registry": TaskRegistryEnum.InMemoryTaskRegistry,
            "task_state_store": TaskStateStoreEnum.InMemoryTaskStateStore,
            "queue": QueueEnum.MapQueue,
        }

    @classmethod
    def from_envs(cls) -> dict[str, Any]:
        """Return settings overridden via ``TLO_*`` environment variables."""
        to_return = {}
        for field in dataclasses.fields(cls):
            env_var = f"TLO_{field.name.upper()}"
            if env_var in os.environ:
                to_return[field.name] = os.environ[env_var]
        return to_return

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

    def update(self, **settings: Any) -> None:
        """Apply keyword overrides directly to the instance."""
        for k, v in settings.items():
            if hasattr(self, k):
                setattr(self, k, v)

    def as_dict(self) -> dict[str, Any]:
        """Return specified settings as a plain dictionary for serialisation."""
        return dataclasses.asdict(self)
