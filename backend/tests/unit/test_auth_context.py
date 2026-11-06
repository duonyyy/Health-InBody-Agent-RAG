import pytest
import jwt
from datetime import datetime, timedelta, timezone
from fastapi import HTTPException
from starlette.requests import Request

from auth.context import (
    CurrentUser,
    get_current_user,
    get_optional_current_user,
    require_legacy_user_match,
)


def _request(headers=None):
    encoded_headers = [
        (name.lower().encode("latin-1"), value.encode("latin-1"))
        for name, value in (headers or {}).items()
    ]
    return Request({"type": "http", "method": "GET", "path": "/", "headers": encoded_headers})


def test_production_mode_ignores_development_identity_header(monkeypatch):
    monkeypatch.setenv("AUTH_MODE", "production")
    request = _request({"X-Dev-User-Id": "user-a"})

    assert get_optional_current_user(request) is None
    with pytest.raises(HTTPException) as exc_info:
        get_current_user(request)
    assert exc_info.value.status_code == 401


def test_development_mode_requires_explicit_valid_header(monkeypatch):
    monkeypatch.setenv("AUTH_MODE", "development")

    identity = get_current_user(_request({"X-Dev-User-Id": "user-a"}))

    assert identity == CurrentUser(subject="user-a", auth_source="development_header")
    with pytest.raises(HTTPException) as exc_info:
        get_current_user(_request({"X-Dev-User-Id": "../../other-user"}))
    assert exc_info.value.status_code == 401


def test_server_context_identity_takes_precedence(monkeypatch):
    monkeypatch.setenv("AUTH_MODE", "development")
    request = _request({"X-Dev-User-Id": "user-b"})
    request.state.current_user = {"sub": "user-a"}

    identity = get_current_user(request)

    assert identity == CurrentUser(subject="user-a", auth_source="server_context")


def test_legacy_path_must_match_current_user_and_be_explicitly_enabled(monkeypatch):
    monkeypatch.setenv("AUTH_MODE", "development")
    monkeypatch.setenv("ENABLE_LEGACY_USER_ENDPOINTS", "true")
    identity = CurrentUser(subject="user-a")

    require_legacy_user_match("user-a", identity)
    with pytest.raises(HTTPException) as exc_info:
        require_legacy_user_match("user-b", identity)
    assert exc_info.value.status_code == 403

    monkeypatch.setenv("ENABLE_LEGACY_USER_ENDPOINTS", "false")
    with pytest.raises(HTTPException) as exc_info:
        require_legacy_user_match("user-a", identity)
    assert exc_info.value.status_code == 404


def test_production_jwt_requires_signature_issuer_audience_and_expiry(monkeypatch):
    monkeypatch.setenv("AUTH_MODE", "production")
    monkeypatch.setenv("JWT_SIGNING_KEY", "test-only-" + "k" * 64)
    monkeypatch.setenv("JWT_ISSUER", "bodywise-test")
    monkeypatch.setenv("JWT_AUDIENCE", "bodywise-test-web")
    now = datetime.now(timezone.utc)
    claims = {
        "sub": "user-a", "iss": "bodywise-test", "aud": "bodywise-test-web",
        "iat": now, "nbf": now, "exp": now + timedelta(minutes=10), "jti": "test-jti",
    }
    token = jwt.encode(claims, "test-only-" + "k" * 64, algorithm="HS256")
    assert get_current_user(_request({"Authorization": f"Bearer {token}"})).subject == "user-a"
    assert get_current_user(_request({"Authorization": f"Bearer {token}", "X-Dev-User-Id": "user-b"})).subject == "user-a"

    for change in (
        {"aud": "other-app"},
        {"iss": "other-issuer"},
        {"exp": now - timedelta(seconds=1)},
        {"sub": "../../bad"},
    ):
        bad = jwt.encode({**claims, **change}, "test-only-" + "k" * 64, algorithm="HS256")
        with pytest.raises(HTTPException) as exc_info:
            get_current_user(_request({"Authorization": f"Bearer {bad}"}))
        assert exc_info.value.status_code == 401

    forged = jwt.encode(claims, "test-only-" + "x" * 64, algorithm="HS256")
    with pytest.raises(HTTPException) as exc_info:
        get_current_user(_request({"Authorization": f"Bearer {forged}"}))
    assert exc_info.value.status_code == 401

    monkeypatch.delenv("JWT_SIGNING_KEY")
    with pytest.raises(HTTPException) as exc_info:
        get_current_user(_request({"Authorization": f"Bearer {token}"}))
    assert exc_info.value.status_code == 401
