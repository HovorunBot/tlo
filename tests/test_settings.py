"""Tests for settings loading and environment coercion."""

from __future__ import annotations

import pytest

from tlo.common import StopBehaviorEnum
from tlo.errors import TloConfigError
from tlo.settings import TloSettings


def test_tick_interval_env_coercion(monkeypatch: pytest.MonkeyPatch) -> None:
    """tick_interval should be coerced from env string to float."""
    monkeypatch.setenv("TLO_TICK_INTERVAL", "0.5")
    settings = TloSettings.load()
    assert settings.tick_interval == 0.5


def test_tick_interval_env_invalid(monkeypatch: pytest.MonkeyPatch) -> None:
    """Invalid tick_interval env should raise configuration error."""
    monkeypatch.setenv("TLO_TICK_INTERVAL", "not-a-number")
    with pytest.raises(TloConfigError):
        TloSettings.load()


def test_custom_dotted_path_passthrough(monkeypatch: pytest.MonkeyPatch) -> None:
    """Non-enum strings should remain untouched to allow dotted paths."""
    monkeypatch.setenv("TLO_QUEUE", "my_app.custom.CustomQueue")
    settings = TloSettings.load()
    assert settings.queue == "my_app.custom.CustomQueue"


def test_stop_behavior_env_coercion(monkeypatch: pytest.MonkeyPatch) -> None:
    """Stop behavior env should coerce to enum."""
    monkeypatch.setenv("TLO_STOP_BEHAVIOR", "Cancel")
    settings = TloSettings.load()
    assert settings.stop_behavior is StopBehaviorEnum.Cancel


def test_stop_behavior_env_invalid(monkeypatch: pytest.MonkeyPatch) -> None:
    """Invalid stop behavior should raise config error."""
    monkeypatch.setenv("TLO_STOP_BEHAVIOR", "NotARealBehavior")
    with pytest.raises(TloConfigError):
        TloSettings.load()
