import pytest

from app.config import ConfigError, Settings, get_settings


def test_missing_token_fails_clearly(monkeypatch):
    monkeypatch.delenv("GUARD_TOKEN", raising=False)
    monkeypatch.setattr("app.config.REPO_ROOT", __import__("pathlib").Path("/nonexistent"))
    monkeypatch.setitem(Settings.model_config, "env_file", None)
    get_settings.cache_clear()
    with pytest.raises(ConfigError, match="GUARD_TOKEN"):
        get_settings()
    get_settings.cache_clear()


def test_blank_token_rejected():
    with pytest.raises(Exception):
        Settings(_env_file=None, guard_token="   ")


def test_token_not_in_repr():
    s = Settings(_env_file=None, guard_token="super-secret-value")
    assert "super-secret-value" not in repr(s)
    assert "super-secret-value" not in str(s.model_dump())
