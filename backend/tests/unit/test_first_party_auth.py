"""First-party JWT is issued only after a real account credential check."""

import os
from contextlib import contextmanager

import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

os.environ.setdefault("DATABASE_URL", "sqlite://")

from api import auth as auth_api
from auth import accounts
from auth.context import CurrentUser, get_current_user
from persistence.database import Base
import persistence.models  # noqa: F401


@compiles(JSONB, "sqlite")
def _compile_jsonb(type_, compiler, **kwargs):
    return "JSON"


@pytest.fixture
def client(monkeypatch):
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)

    @contextmanager
    def session():
        with factory() as db:
            try:
                yield db
                db.commit()
            except Exception:
                db.rollback()
                raise

    monkeypatch.setattr(accounts, "session_scope", session)
    monkeypatch.setattr(auth_api, "_rate_limit", lambda request, username: None)
    monkeypatch.setattr(auth_api, "_rate_limit_refresh", lambda request: None)
    monkeypatch.setenv("AUTH_MODE", "production")
    monkeypatch.setenv("JWT_SIGNING_KEY", "test-only-" + "k" * 64)
    monkeypatch.setenv("JWT_ISSUER", "bodywise-test")
    monkeypatch.setenv("JWT_AUDIENCE", "bodywise-test-web")
    app = FastAPI()
    app.include_router(auth_api.router)

    @app.get("/whoami")
    def whoami(user: CurrentUser = Depends(get_current_user)):
        return {"subject": user.subject}

    yield TestClient(app)
    engine.dispose()


def test_register_login_and_signed_identity(client):
    credentials = {"username": "Alice.One", "password": "a-very-long-test-password"}
    first = client.post("/auth/register", json=credentials)
    assert first.status_code == 201
    token = first.json()["access_token"]
    assert "refresh_token" in first.json()
    subject = client.get("/whoami", headers={"Authorization": f"Bearer {token}"}).json()["subject"]
    assert subject.startswith("bw_")
    assert client.post("/auth/register", json=credentials).status_code == 409
    assert client.post("/auth/login", json={**credentials, "password": "wrong-password-123"}).status_code == 401
    second = client.post("/auth/login", json=credentials)
    assert second.status_code == 200
    assert "refresh_token" in second.json()
    assert client.get("/whoami", headers={"Authorization": f"Bearer {second.json()['access_token']}"}).json()["subject"] == subject
    assert client.get("/whoami", headers={"X-Dev-User-Id": "attacker"}).status_code == 401


def test_refresh_token_rotation_and_revocation(client):
    credentials = {"username": "Bob.Refresh", "password": "a-very-long-test-password"}
    reg = client.post("/auth/register", json=credentials)
    assert reg.status_code == 201
    initial_refresh = reg.json()["refresh_token"]

    # 1. Rotate refresh token
    refreshed = client.post("/auth/refresh", json={"refresh_token": initial_refresh})
    assert refreshed.status_code == 200
    new_access = refreshed.json()["access_token"]
    new_refresh = refreshed.json()["refresh_token"]
    assert new_refresh != initial_refresh

    # Verify new access token works
    who = client.get("/whoami", headers={"Authorization": f"Bearer {new_access}"})
    assert who.status_code == 200
    assert who.json()["subject"].startswith("bw_")

    # 2. Replay attack prevention: old refresh token must be rejected
    replayed = client.post("/auth/refresh", json={"refresh_token": initial_refresh})
    assert replayed.status_code == 401

    # 3. Logout revokes token
    logout = client.post("/auth/logout", json={"refresh_token": new_refresh})
    assert logout.status_code == 200
    revoked_refresh = client.post("/auth/refresh", json={"refresh_token": new_refresh})
    assert revoked_refresh.status_code == 401


def test_refresh_token_invalid_rejected(client):
    res = client.post("/auth/refresh", json={"refresh_token": "non-existent-random-token-here-123456789"})
    assert res.status_code == 401


def test_rate_limit_is_shared_and_fails_closed(monkeypatch):
    class FakeRedis:
        def __init__(self):
            self.counts = {}
        def incr(self, key):
            self.counts[key] = self.counts.get(key, 0) + 1
            return self.counts[key]
        def expire(self, key, seconds):
            assert seconds == 60
    redis = FakeRedis()
    monkeypatch.setattr(auth_api, "get_redis_client", lambda: redis)
    from starlette.requests import Request
    from fastapi import HTTPException
    request = Request({"type": "http", "method": "POST", "path": "/auth/login", "headers": [], "client": ("127.0.0.1", 1234)})
    for _ in range(5):
        auth_api._rate_limit(request, "Alice")
    with pytest.raises(HTTPException) as exc:
        auth_api._rate_limit(request, "alice")
    assert exc.value.status_code == 429
    monkeypatch.setattr(auth_api, "get_redis_client", lambda: None)
    with pytest.raises(HTTPException) as exc:
        auth_api._rate_limit(request, "bob")
    assert exc.value.status_code == 503
