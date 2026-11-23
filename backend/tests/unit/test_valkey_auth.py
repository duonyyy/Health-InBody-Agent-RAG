"""Tests for Valkey/Redis authentication configuration."""

import os
from unittest.mock import MagicMock, patch

from core import cache as cache_module


def test_valkey_password_configured(monkeypatch):
    """Xac nhan password duoc truyen dung vao StrictRedis khi co REDIS_PASSWORD."""
    monkeypatch.setenv("REDIS_PASSWORD", "super-secret-valkey-pass")
    monkeypatch.setattr(cache_module, "_redis_client", None)
    monkeypatch.setattr(cache_module, "_redis_last_attempt", 0.0)
    monkeypatch.setattr(cache_module, "_redis_probe_in_flight", False)

    mock_client = MagicMock()
    mock_client.ping.return_value = True

    with patch("redis.StrictRedis", return_value=mock_client) as mock_redis_cls:
        client = cache_module.get_redis_client(timeout=1.0)
        assert client is mock_client
        mock_redis_cls.assert_called_once()
        _, kwargs = mock_redis_cls.call_args
        assert kwargs.get("password") == "super-secret-valkey-pass"


def test_valkey_no_password_backward_compatible(monkeypatch):
    """Xac nhan khong truyen password khi REDIS_PASSWORD khong ton tai."""
    monkeypatch.delenv("REDIS_PASSWORD", raising=False)
    monkeypatch.setattr(cache_module, "_redis_client", None)
    monkeypatch.setattr(cache_module, "_redis_last_attempt", 0.0)
    monkeypatch.setattr(cache_module, "_redis_probe_in_flight", False)

    mock_client = MagicMock()
    mock_client.ping.return_value = True

    with patch("redis.StrictRedis", return_value=mock_client) as mock_redis_cls:
        client = cache_module.get_redis_client(timeout=1.0)
        assert client is mock_client
        mock_redis_cls.assert_called_once()
        _, kwargs = mock_redis_cls.call_args
        assert "password" not in kwargs


def test_celery_broker_url_with_password(monkeypatch):
    """Xac nhan DEFAULT_CELERY_BROKER_URL format dung URL voi password."""
    monkeypatch.setenv("REDIS_HOST", "my-valkey")
    monkeypatch.setenv("REDIS_PORT", "6380")
    monkeypatch.setenv("REDIS_DB", "2")
    monkeypatch.setenv("REDIS_PASSWORD", "valkey-token-123")
    monkeypatch.delenv("CELERY_BROKER_URL", raising=False)

    import importlib
    from core import config as config_mod

    importlib.reload(config_mod)

    assert config_mod.DEFAULT_CELERY_BROKER_URL == "redis://:valkey-token-123@my-valkey:6380/2"

    # Don dep env sau test
    monkeypatch.delenv("REDIS_PASSWORD", raising=False)
    importlib.reload(config_mod)
