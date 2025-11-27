"""Tests for settings loading and environment coercion."""

from __future__ import annotations

import dataclasses

import pytest

from tlo.common import StopBehaviorEnum
from tlo.errors import TloConfigError
from tlo.settings import Loader, SettingsBase, TloSettings, TloSettingsKwargs


# Module-level optional nested settings for reliable type resolution
@dataclasses.dataclass
class _OptInner(SettingsBase):
    host: str = "localhost"


@dataclasses.dataclass
class _OptOuter(SettingsBase):
    inner: _OptInner | None = None


def test_tick_interval_env_coercion(monkeypatch: pytest.MonkeyPatch) -> None:
    """tick_interval should be coerced from env string to float."""
    monkeypatch.setenv("TLO_TICK_INTERVAL", "0.5")
    settings = Loader().load(TloSettings, root_prefix="TLO")
    assert settings.tick_interval == 0.5


def test_tick_interval_env_invalid(monkeypatch: pytest.MonkeyPatch) -> None:
    """Invalid tick_interval env should raise configuration error."""
    monkeypatch.setenv("TLO_TICK_INTERVAL", "not-a-number")
    with pytest.raises(TloConfigError):
        Loader().load(TloSettings, root_prefix="TLO")


def test_custom_dotted_path_passthrough(monkeypatch: pytest.MonkeyPatch) -> None:
    """Non-enum strings should remain untouched to allow dotted paths."""
    monkeypatch.setenv("TLO_QUEUE", "my_app.custom.CustomQueue")
    settings = Loader().load(TloSettings, root_prefix="TLO")
    assert settings.queue == "my_app.custom.CustomQueue"


def test_stop_behavior_env_coercion(monkeypatch: pytest.MonkeyPatch) -> None:
    """Stop behavior env should coerce to enum."""
    monkeypatch.setenv("TLO_STOP_BEHAVIOR", "Cancel")
    settings = Loader().load(TloSettings, root_prefix="TLO")
    assert settings.stop_behavior is StopBehaviorEnum.Cancel


def test_stop_behavior_env_invalid(monkeypatch: pytest.MonkeyPatch) -> None:
    """Invalid stop behavior should raise config error."""
    monkeypatch.setenv("TLO_STOP_BEHAVIOR", "NotARealBehavior")
    with pytest.raises(TloConfigError):
        Loader().load(TloSettings, root_prefix="TLO")


def test_settings_kwargs_matches_settings_fields() -> None:
    """Kwargs TypedDict should stay in sync with TloSettings fields."""
    settings_fields = {field.name for field in dataclasses.fields(TloSettings)}
    kwargs_fields = set(TloSettingsKwargs.__annotations__)
    assert settings_fields == kwargs_fields


@dataclasses.dataclass
class SettingsForTest(SettingsBase):
    """Settings fixture for prefix and alias checks."""

    foo: str = dataclasses.field(default="default_foo")
    bar: int = dataclasses.field(default=0, metadata={"env_aliases": ["ALIAS_BAR"], "env_coercer": int})


def test_settings_base_prefix_and_aliases(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test SettingsBase prefix handling and env_aliases."""
    # Test defaults
    s1 = Loader().load(SettingsForTest, root_prefix="TEST")
    assert s1.foo == "default_foo"
    assert s1.bar == 0

    # Test prefix
    monkeypatch.setenv("TEST_FOO", "env_foo")
    s2 = Loader().load(SettingsForTest, root_prefix="TEST")
    assert s2.foo == "env_foo"

    # Test alias (must be prefixed when root_prefix is provided)
    monkeypatch.setenv("TEST_ALIAS_BAR", "42")
    s3 = Loader().load(SettingsForTest, root_prefix="TEST")
    assert s3.bar == 42

    # Test priority (kwargs > env)
    s4 = Loader().load(SettingsForTest, root_prefix="TEST", overrides={"bar": 100})
    assert s4.bar == 100


@dataclasses.dataclass
class DatabaseSettings(SettingsBase):
    """Database settings for nesting tests."""

    host: str = dataclasses.field(default="localhost")
    port: int = dataclasses.field(default=5432, metadata={"env_coercer": int})


@dataclasses.dataclass
class AppSettings(SettingsBase):
    """Application settings with nested database config."""

    db: DatabaseSettings = dataclasses.field(default_factory=DatabaseSettings)
    debug: bool = dataclasses.field(default=False)


def test_nested_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test loading of nested settings."""
    # Test defaults
    s1 = Loader().load(AppSettings, root_prefix="APP")
    assert s1.db.host == "localhost"
    assert s1.db.port == 5432

    # Test nested env vars (APP_DB__HOST)
    monkeypatch.setenv("APP_DB__HOST", "db.example.com")
    monkeypatch.setenv("APP_DB__PORT", "9999")
    s2 = Loader().load(AppSettings, root_prefix="APP")
    assert s2.db.host == "db.example.com"
    assert s2.db.port == 9999

    # Test nested kwargs
    s3 = Loader().load(AppSettings, root_prefix="APP", overrides={"db": {"host": "kwarg.host", "port": 1111}})
    assert s3.db.host == "kwarg.host"
    assert s3.db.port == 1111


@dataclasses.dataclass
class ConfigSettings(SettingsBase):
    """Config settings for deep nesting."""

    db_name: str = dataclasses.field(default="default_db")


@dataclasses.dataclass
class DeepDatabaseSettings(SettingsBase):
    """Intermediate nested settings level."""

    config: ConfigSettings = dataclasses.field(default_factory=ConfigSettings)


@dataclasses.dataclass
class RootSettings(SettingsBase):
    """Root settings used for deep nesting tests."""

    database: DeepDatabaseSettings = dataclasses.field(default_factory=DeepDatabaseSettings)


def test_deeply_nested_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test loading of multiple levels of nested settings."""
    # Test defaults
    s1 = Loader().load(RootSettings, root_prefix="TLO")
    assert s1.database.config.db_name == "default_db"

    monkeypatch.setenv("TLO_DATABASE__CONFIG__DB_NAME", "deep_db")
    s2 = Loader().load(RootSettings, root_prefix="TLO")
    assert s2.database.config.db_name == "deep_db"


def test_combined_loading_priority(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test combined loading from defaults, env vars, and kwargs with priority."""
    # Setup:
    # - host: default="localhost"
    # - port: env="5432" (overrides default 8000)
    # - debug: kwarg=True (overrides env False)

    @dataclasses.dataclass
    class CombinedSettings(SettingsBase):
        host: str = dataclasses.field(default="localhost")
        port: int = dataclasses.field(default=8000, metadata={"env_coercer": int})
        debug: bool = dataclasses.field(
            default=False,
            metadata={"env_coercer": lambda x: x.lower() == "true"},
        )

    monkeypatch.setenv("COMBINED_PORT", "5432")
    monkeypatch.setenv("COMBINED_DEBUG", "false")

    # Load with kwarg override for debug
    s = Loader().load(CombinedSettings, root_prefix="COMBINED", overrides={"debug": True})

    assert s.host == "localhost"  # From default
    assert s.port == 5432  # From env
    assert s.debug is True  # From kwarg (overrides env)


def test_settings_field_explicit_args() -> None:
    """Dataclass field should preserve metadata for env lookups."""

    @dataclasses.dataclass
    class MetadataSettings(SettingsBase):
        value: int = dataclasses.field(
            default=1,
            init=False,
            repr=False,
            hash=True,
            compare=False,
            metadata={"extra": "meta", "env_aliases": ["ALIAS"]},
        )

    (field,) = dataclasses.fields(MetadataSettings)
    assert field.default == 1
    assert field.init is False
    assert field.repr is False
    assert field.hash is True
    assert field.compare is False
    assert field.metadata["extra"] == "meta"
    assert field.metadata["env_aliases"] == ["ALIAS"]


def test_aliases_respect_prefix(monkeypatch: pytest.MonkeyPatch) -> None:
    """Aliases must be checked with the same prefix when a root_prefix is provided.

    Given a field named DB_NAME with alias DB_FILE_NAME and root prefix TLO, the loader
    must accept TLO_DB_NAME and TLO_DB_FILE_NAME, but ignore unprefixed DB_NAME and
    DB_FILE_NAME.
    """

    @dataclasses.dataclass
    class AliasCfg(SettingsBase):
        db_name: str = dataclasses.field(default="default", metadata={"env_aliases": ["DB_FILE_NAME"]})

    # Set only unprefixed vars: should be ignored when prefix is provided
    monkeypatch.setenv("DB_NAME", "unprefixed-primary")
    monkeypatch.setenv("DB_FILE_NAME", "unprefixed-alias")
    s1 = Loader().load(AliasCfg, root_prefix="TLO")
    assert s1.db_name == "default"

    # Set prefixed primary
    monkeypatch.setenv("TLO_DB_NAME", "prefixed-primary")
    s2 = Loader().load(AliasCfg, root_prefix="TLO")
    assert s2.db_name == "prefixed-primary"

    # Primary absent, prefixed alias present
    monkeypatch.delenv("TLO_DB_NAME", raising=False)
    monkeypatch.setenv("TLO_DB_FILE_NAME", "prefixed-alias")
    s3 = Loader().load(AliasCfg, root_prefix="TLO")
    assert s3.db_name == "prefixed-alias"


def test_aliases_without_prefix(monkeypatch: pytest.MonkeyPatch) -> None:
    """When no root prefix is given, unprefixed aliases are used verbatim."""

    @dataclasses.dataclass
    class AliasCfg(SettingsBase):
        value: int = dataclasses.field(default=0, metadata={"env_aliases": ["ALT_VALUE"], "env_coercer": int})

    # With no prefix, primary name is field name uppercased; alias is used as provided
    monkeypatch.setenv("ALT_VALUE", "123")
    s = Loader().load(AliasCfg)
    assert s.value == 123


def test_metadata_parsing_various_alias_types(monkeypatch: pytest.MonkeyPatch) -> None:
    """Metadata parser should accept string, list, and tuple forms for env_aliases."""

    @dataclasses.dataclass
    class S1(SettingsBase):
        a: int = dataclasses.field(default=0, metadata={"env_aliases": ["A1"], "env_coercer": int})

    @dataclasses.dataclass
    class S2(SettingsBase):
        b: int = dataclasses.field(default=0, metadata={"env_aliases": ["B1", "B2"], "env_coercer": int})

    @dataclasses.dataclass
    class S3(SettingsBase):
        c: int = dataclasses.field(default=0, metadata={"env_aliases": ("C1",), "env_coercer": int})

    monkeypatch.setenv("A1", "10")
    assert Loader().load(S1).a == 10

    monkeypatch.setenv("B2", "20")
    assert Loader().load(S2).b == 20

    monkeypatch.setenv("C1", "30")
    assert Loader().load(S3).c == 30


def test_no_prefix_env_lookup(monkeypatch: pytest.MonkeyPatch) -> None:
    """When root_prefix is None/empty, loader should resolve unprefixed env names."""
    # Use TloSettings and set unprefixed env var name
    monkeypatch.setenv("TICK_INTERVAL", "2.5")
    settings = Loader().load(TloSettings)
    assert settings.tick_interval == 2.5


def test_prefixed_env_beats_alias(monkeypatch: pytest.MonkeyPatch) -> None:
    """Primary env var (with prefix) should have priority over any aliases."""

    @dataclasses.dataclass
    class AliasSettings(SettingsBase):
        value: int = dataclasses.field(default=0, metadata={"env_aliases": ["ALIAS_VALUE"], "env_coercer": int})

    # Set both the prefixed primary and the alias with different values
    monkeypatch.setenv("PFX_VALUE", "123")
    monkeypatch.setenv("ALIAS_VALUE", "999")
    s = Loader().load(AliasSettings, root_prefix="PFX")
    assert s.value == 123


def test_nested_override_instantiated_object() -> None:
    """Passing a fully-instantiated nested Settings object should be used as-is."""

    @dataclasses.dataclass
    class Inner(SettingsBase):
        host: str = "localhost"
        port: int = dataclasses.field(default=5432, metadata={"env_coercer": int})

    @dataclasses.dataclass
    class Outer(SettingsBase):
        inner: Inner = dataclasses.field(default_factory=Inner)

    custom = Inner(host="example.com", port=7777)
    s = Loader().load(Outer, root_prefix="OUT", overrides={"inner": custom})
    assert s.inner is custom
    assert s.inner.host == "example.com"
    assert s.inner.port == 7777


def test_nested_override_none_sets_none() -> None:
    """Explicit None for a nested field should be preserved as None."""

    @dataclasses.dataclass
    class Inner(SettingsBase):
        x: int = 1

    @dataclasses.dataclass
    class Outer(SettingsBase):
        inner: Inner = dataclasses.field(default_factory=Inner)

    s = Loader().load(Outer, root_prefix="OUT", overrides={"inner": None})
    assert s.inner is None


@pytest.mark.parametrize("val", ["1", "true", "TRUE", "on", "yes", "YeS"])
def test_panic_mode_truthy(monkeypatch: pytest.MonkeyPatch, val: str) -> None:
    """panic_mode should be True for a set of truthy string values (case-insensitive)."""
    monkeypatch.setenv("TLO_PANIC_MODE", val)
    s = Loader().load(TloSettings, root_prefix="TLO")
    assert s.panic_mode is True


@pytest.mark.parametrize("val", ["0", "false", "FALSE", "off", "no", "No"])
def test_panic_mode_falsy(monkeypatch: pytest.MonkeyPatch, val: str) -> None:
    """panic_mode should be False for a set of falsy string values (case-insensitive)."""
    monkeypatch.setenv("TLO_PANIC_MODE", val)
    s = Loader().load(TloSettings, root_prefix="TLO")
    assert s.panic_mode is False


def test_panic_mode_invalid(monkeypatch: pytest.MonkeyPatch) -> None:
    """Invalid boolean string for panic_mode should raise TloConfigError."""
    monkeypatch.setenv("TLO_PANIC_MODE", "maybe")
    with pytest.raises(TloConfigError):
        Loader().load(TloSettings, root_prefix="TLO")


def test_optional_nested_defaults_none_env_populates(monkeypatch: pytest.MonkeyPatch) -> None:
    """Optional nested settings with default None should populate from nested env vars."""
    monkeypatch.setenv("OUT_INNER__HOST", "env-host")
    s = Loader().load(_OptOuter, root_prefix="OUT")
    assert s.inner is not None
    assert s.inner.host == "env-host"


def test_optional_nested_override_none_preserved() -> None:
    """Explicit None override for Optional nested field should be preserved as None."""
    s = Loader().load(_OptOuter, root_prefix="OUT", overrides={"inner": None})
    assert s.inner is None
