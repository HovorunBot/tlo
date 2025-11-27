"""Settings for the TLO runtime and useful functionality to work with them."""

from __future__ import annotations

import dataclasses
import os
from typing import TYPE_CHECKING, Any, NotRequired, TypedDict, Unpack, cast, get_args, get_type_hints

from tlo.utils.coercers import enum_or_original, identity, to_bool

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping

from tlo.common import (
    ExecutorEnum,
    LockerEnum,
    QueueEnum,
    SchedulerEnum,
    StopBehaviorEnum,
    TaskRegistryEnum,
    TaskStateStoreEnum,
)
from tlo.errors import TloConfigError
from tlo.executor.executor import LocalExecutor

_MISSING: Any = dataclasses.MISSING
type T = Any


@dataclasses.dataclass(frozen=True)
class FieldEnvMeta:
    """Typed view over supported field metadata for env lookups.

    Rules (strict):
    - env_aliases: must be a list/tuple of strings when provided. Aliases are specified
      WITHOUT the root prefix; the loader will prepend the root prefix (and underscore) if one is
      supplied during loading. When no root prefix is supplied, aliases are used verbatim.
    - env_coercer: must be a Callable[[str], Any] when provided.
    """

    aliases: tuple[str, ...] = ()
    coercer: Callable[[str], Any] = identity


@dataclasses.dataclass
class SettingsBase:
    """Base class for settings.

    Notes on environment variable resolution:
    - The loader constructs environment variable names using a caller-provided
      root prefix and a double-underscore-delimited path of field names.
    - Final format: `PREFIX_SEG1__SEG2__...` where `PREFIX_` is optional and
      provided by the caller (e.g., `"TLO"`).
    - Settings classes themselves do not define or own a prefix.
    """

    def as_dict(self) -> dict[str, Any]:
        """Return settings as a dictionary."""
        return dataclasses.asdict(self)


class Loader:
    """Responsible for loading settings from defaults, environment variables, and kwargs."""

    def load[TSettings: SettingsBase](
        self,
        settings_cls: type[TSettings],
        root_prefix: str = "",
        parents: list[str] | None = None,
        overrides: dict[str, Any] | None = None,
    ) -> TSettings:
        """Load settings from defaults, environment variables, and kwargs.

        :param settings_cls: The settings class to instantiate.
        :param root_prefix: Optional root prefix for env vars (e.g., "TLO").
            If None, no prefix is applied. The prefix is owned by the caller,
            not by the settings class itself.
        :param parents: List of parent path segments for nested settings.
        :param overrides: Dictionary of override values.
        :returns: Instantiated settings object.
        """
        root_prefix = "" if root_prefix is None else root_prefix
        parents = [] if parents is None else parents
        overrides = {} if overrides is None else overrides

        init_kwargs: dict[str, Any] = {}
        try:
            type_hints = get_type_hints(settings_cls)
        except NameError:
            # In some cases (e.g., classes defined inside functions) local symbols used
            # in annotations may not be resolvable here. Fall back to raw field.types.
            type_hints = {}

        for field in dataclasses.fields(settings_cls):
            self._load_field(field, type_hints, parents, root_prefix, overrides, init_kwargs)

        return settings_cls(**init_kwargs)

    def _load_field(
        self,
        field: dataclasses.Field[T],
        type_hints: Mapping[str, Any],
        parents: list[str],
        root_prefix: str,
        overrides: dict[str, Any],
        init_kwargs: dict[str, Any],
    ) -> None:
        field_name = field.name
        field_type = self._resolve_field_type(type_hints, field_name, field)
        nested_settings_type = None
        if self._has_settings_type_hint(field_type):
            # Unwrap Optional/Union to detect nested SettingsBase types
            nested_settings_type = self._unwrap_nested_settings_type(field_type)
        current_segments = self._build_current_segments(parents, field_name)

        if nested_settings_type is not None:
            value = self._load_nested_settings(
                field_name, nested_settings_type, root_prefix, current_segments, overrides
            )
        else:
            value = self._load_scalar_field(field, field_name, overrides, root_prefix, current_segments)

        if value is _MISSING:
            return

        init_kwargs[field.name] = value

    def _load_nested_settings(
        self,
        field_name: str,
        nested_settings_type: type[SettingsBase],
        root_prefix: str,
        current_segments: list[str],
        overrides: dict[str, Any],
    ) -> Any:
        return self._load_nested_field(
            field_name=field_name,
            field_type=nested_settings_type,
            root_prefix=root_prefix,
            current_segments=current_segments,
            overrides=overrides,
        )

    def _resolve_field_type(self, type_hints: Mapping[str, Any], field_name: str, field: dataclasses.Field[Any]) -> Any:
        # field.type might be a string due to __future__ annotations; prefer evaluated type hints
        return type_hints.get(field_name, field.type)

    def _has_settings_type_hint(self, field_type: Any) -> bool:
        if isinstance(field_type, type) and issubclass(field_type, SettingsBase):
            return True
        return any(isinstance(arg, type) and issubclass(arg, SettingsBase) for arg in get_args(field_type))

    def _unwrap_nested_settings_type(self, field_type: Any) -> type[SettingsBase]:
        """Return the SettingsBase subclass for nested fields or raise for invalid hints.

        Accepts direct subclasses or Optional/Union forms that include exactly one
        SettingsBase subclass plus an optional NoneType.
        """
        if isinstance(field_type, type) and issubclass(field_type, SettingsBase):
            return field_type

        args = tuple(get_args(field_type))
        if len(args) > 2:  # noqa: PLR2004
            msg = f"{field_type!r} is not a SettingsBase or Optional[SettingsBase]"
            raise TypeError(msg)

        settings_args = [arg for arg in args if isinstance(arg, type) and issubclass(arg, SettingsBase)]
        if len(settings_args) > 1:
            msg = f"{field_type!r} is not a SettingsBase or Optional[SettingsBase]"
            raise TypeError(msg)

        if len(settings_args) == len(args):
            return settings_args[0]

        none_args = [arg for arg in args if arg is type(None)]

        if settings_args and len(settings_args) == 1 and len(settings_args) + len(none_args) == len(args):
            return settings_args[0]

        msg = f"{field_type!r} is not a SettingsBase or Optional[SettingsBase]"
        raise TypeError(msg)

    def _build_current_segments(self, parents: list[str], field_name: str) -> list[str]:
        return [*parents, field_name.upper()]

    def _load_nested_field(
        self,
        *,
        field_name: str,
        field_type: Any,
        root_prefix: str,
        current_segments: list[str],
        overrides: dict[str, Any],
    ) -> Any:
        # Check overrides for nested dict, object, or explicit None
        if field_name in overrides and overrides.get(field_name) is None:
            return None

        nested_val = overrides.get(field_name)

        # Fully-instantiated settings object
        if nested_val is not None and isinstance(field_type, type) and isinstance(nested_val, field_type):
            return nested_val

        # Dict overrides for nested populate
        nested_overrides = nested_val if isinstance(nested_val, dict) else {}
        if nested_overrides or self._has_env_for_nested(root_prefix, current_segments):
            return self.load(
                field_type,
                root_prefix=root_prefix,
                parents=current_segments,
                overrides=nested_overrides,
            )
        # No override and no env for nested path: preserve dataclass default (which may be None)
        return _MISSING

    def _load_scalar_field(
        self,
        field: dataclasses.Field[T],
        field_name: str,
        overrides: dict[str, Any],
        root_prefix: str,
        current_segments: list[str],
    ) -> Any:
        # 1. kwargs overrides
        if field_name in overrides:
            return overrides[field_name]

        # 2. environment
        env_value = self._load_from_env(field, root_prefix, current_segments)
        if env_value is not _MISSING:
            return env_value

        # 3. signal to use dataclass default
        return _MISSING

    def _load_from_env[T](self, field: dataclasses.Field[T], root_prefix: str, path_segments: list[str]) -> Any:
        """Load field value from environment variables.

        Environment variable names are constructed as follows:
        - Join `path_segments` (already uppercased) using the double underscore
          delimiter `__`, e.g., `DB__HOST` or `DATABASE__CONFIG__DB_NAME`.
        - If `root_prefix` is a non-empty string, prepend it and a single
          underscore: `"{root_prefix}_{path}"`.
        - The final format is therefore: `PREFIX_SEG1__SEG2__...`.

        :param field: The dataclass field to load.
        :param root_prefix: The root prefix (e.g., "TLO"). Empty string means no prefix.
        :param path_segments: List of path segments for nested fields.
        :returns: The loaded value coerced if necessary, or dataclasses.MISSING if not found.
        """
        # Parse field metadata once into a typed helper
        env_meta = self._parse_env_metadata(field)

        # Determine potential env var names (search order matters)
        candidates: list[str] = []

        # Construct path string: SEGMENT__SEGMENT
        path_str = "__".join(path_segments)

        # Primary candidate: ROOT_PREFIX + _ + PATH_STR (if prefix exists)
        if root_prefix:
            candidates.append(f"{root_prefix}_{path_str}")
        else:
            candidates.append(path_str)

        # Alias candidates
        if env_meta.aliases:
            if root_prefix:
                # When a prefix is provided, aliases must respect the same prefix
                candidates.extend([f"{root_prefix}_{alias}" for alias in env_meta.aliases])
            else:
                # No prefix: use aliases verbatim
                candidates.extend(list(env_meta.aliases))

        # Check env vars
        value = None
        for env_name in candidates:
            if env_name in os.environ:
                value = os.environ[env_name]
                break

        if value is not None:
            # Apply coercer if present
            if env_meta.coercer is not None:
                try:
                    value = env_meta.coercer(value)
                except ValueError as exc:
                    msg = f"{value!r} is not a valid value for {field.name!r}"
                    raise TloConfigError(msg) from exc
            return value

        return dataclasses.MISSING

    def _parse_env_metadata(self, field: dataclasses.Field[Any]) -> FieldEnvMeta:
        """Parse `field.metadata` into a typed structure.

        Strict rules:
        - `env_aliases` when provided MUST be a list/tuple of strings; otherwise TypeError.
        - `env_coercer` when provided MUST be callable; otherwise TypeError.
        - Extra keys are ignored.
        """
        md: Mapping[str, Any] = field.metadata
        return FieldEnvMeta(
            aliases=self._get_raw_aliases_from_metadata(md), coercer=self._get_coercer_from_metadata(md)
        )

    def _get_coercer_from_metadata(self, md: Mapping[str, Any]) -> Callable[[str], Any]:
        coercer = md.get("env_coercer")
        match coercer:
            case None:
                return identity
            case coercer if callable(coercer):
                return cast("Callable[[str], Any]", coercer)
            case _:
                msg = f"`env_coercer` must be callable when provided, got {type(coercer)!r}"
                raise TypeError(msg)

    def _get_raw_aliases_from_metadata(self, md: Mapping[str, Any]) -> tuple[str, ...]:
        match raw_aliases := md.get("env_aliases", None):
            case None:
                return ()
            case list() | tuple() if not all(isinstance(a, str) for a in raw_aliases):
                msg = "env_aliases must be a list/tuple of strings"
                raise TypeError(msg)
            case list() | tuple():
                return tuple(raw_aliases)
            case _:
                msg = f"`env_aliases` must be a list/tuple of strings when provided, got {type(raw_aliases)!r}"
                raise TypeError(msg)

    @staticmethod
    def _has_env_for_nested(root_prefix: str, path_segments: list[str]) -> bool:
        """Return True if any environment variable targets children of the given nested path.

        We detect presence by checking if any env var starts with the composed prefix
        of the path plus the required double-underscore separator for a child, e.g.:
        - root_prefix="TLO", path=["DB"] -> look for keys starting with "TLO_DB__"
        - root_prefix="" (no prefix), path=["DATABASE", "CONFIG"] -> "DATABASE__CONFIG__"
        """
        base = "__".join(path_segments) + "__"
        if root_prefix:
            base = f"{root_prefix}_{base}"
        return any(key.startswith(base) for key in os.environ)


class TloSettingsKwargs(TypedDict):
    """Kwargs accepted by :meth:`TloSettings.load`."""

    task_registry: NotRequired[TaskRegistryEnum | str]
    task_state_store: NotRequired[TaskStateStoreEnum | str]
    queue: NotRequired[QueueEnum | str]
    scheduler: NotRequired[SchedulerEnum | str]
    executor: NotRequired[ExecutorEnum | str]
    locker: NotRequired[LockerEnum | str]
    tick_interval: NotRequired[float]
    default_queue: NotRequired[str]
    stop_behavior: NotRequired[StopBehaviorEnum]
    panic_mode: NotRequired[bool]


@dataclasses.dataclass
class TloSettings(SettingsBase):
    """Strongly typed configuration holder for TLO runtime services."""

    task_registry: TaskRegistryEnum | str = dataclasses.field(
        default=TaskRegistryEnum.InMemoryTaskRegistry,
        metadata={"env_coercer": lambda v: enum_or_original(v, TaskRegistryEnum)},
    )
    task_state_store: TaskStateStoreEnum | str = dataclasses.field(
        default=TaskStateStoreEnum.InMemoryTaskStateStore,
        metadata={"env_coercer": lambda v: enum_or_original(v, TaskStateStoreEnum)},
    )
    queue: QueueEnum | str = dataclasses.field(
        default=QueueEnum.MapQueue,
        metadata={"env_coercer": lambda v: enum_or_original(v, QueueEnum)},
    )
    scheduler: SchedulerEnum | str = dataclasses.field(
        default=SchedulerEnum.SimpleScheduler,
        metadata={"env_coercer": lambda v: enum_or_original(v, SchedulerEnum)},
    )
    executor: ExecutorEnum | str = dataclasses.field(
        default=LocalExecutor.get_name(),
        metadata={"env_coercer": lambda v: enum_or_original(v, ExecutorEnum)},
    )
    locker: LockerEnum | str = dataclasses.field(
        default=LockerEnum.InMemoryLocker,
        metadata={"env_coercer": lambda v: enum_or_original(v, LockerEnum)},
    )
    tick_interval: float = dataclasses.field(
        default=1.0,
        metadata={"env_coercer": float},
    )
    default_queue: str = dataclasses.field(
        default="default",
    )
    stop_behavior: StopBehaviorEnum = dataclasses.field(
        default=StopBehaviorEnum.Drain,
        metadata={"env_coercer": lambda v: StopBehaviorEnum(v)},
    )
    panic_mode: bool = dataclasses.field(
        default=False,
        metadata={"env_coercer": to_bool},
    )

    def update(self, **settings: Unpack[TloSettingsKwargs]) -> None:
        """Apply keyword overrides directly to the instance."""
        for k, v in settings.items():
            if hasattr(self, k):
                setattr(self, k, v)
