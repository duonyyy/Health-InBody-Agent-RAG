"""Resolve authenticated identity without trusting client-supplied user IDs."""

import os
import re
from datetime import datetime, timedelta, timezone
from dataclasses import dataclass
from typing import Any, Optional
from uuid import uuid4

import jwt

from fastapi import Depends, HTTPException, Request, status


_SUBJECT_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:@-]{0,127}$")


@dataclass(frozen=True)
class CurrentUser:
    """Minimal server-owned identity passed into ownership-scoped services."""

    subject: str
    auth_source: str = "server_context"
    scopes: tuple[str, ...] = ()


def auth_mode() -> str:
    return os.getenv("AUTH_MODE", "production").strip().lower()


def _validated_subject(value: Any) -> Optional[str]:
    if value is None:
        return None
    subject = str(value).strip()
    if not _SUBJECT_PATTERN.fullmatch(subject):
        return None
    return subject


def _server_owned_identity(request: Request) -> Optional[CurrentUser]:
    identity = getattr(request.state, "current_user", None)
    if isinstance(identity, CurrentUser):
        return identity
    if isinstance(identity, dict):
        subject = _validated_subject(identity.get("subject") or identity.get("sub"))
        if subject:
            scopes = identity.get("scopes") or []
            if not isinstance(scopes, (list, tuple)):
                scopes = []
            return CurrentUser(subject=subject, auth_source="server_context", scopes=tuple(scopes))
    subject = _validated_subject(getattr(identity, "subject", None))
    if subject:
        return CurrentUser(subject=subject, auth_source="server_context")
    return None


def _jwt_configuration() -> Optional[tuple[str, str, str]]:
    key = os.getenv("JWT_SIGNING_KEY", "")
    issuer = os.getenv("JWT_ISSUER", "").strip()
    audience = os.getenv("JWT_AUDIENCE", "").strip()
    if len(key.encode("utf-8")) < 32 or not issuer or not audience:
        return None
    return key, issuer, audience


def issue_access_token(subject: str, scopes: tuple[str, ...] = (), ttl_seconds: int = 900) -> str:
    """Issue a short-lived first-party token only after a caller authenticates the user."""
    config = _jwt_configuration()
    if config is None or _validated_subject(subject) != subject:
        raise RuntimeError("JWT authentication is not configured")
    key, issuer, audience = config
    now = datetime.now(timezone.utc)
    return jwt.encode(
        {"sub": subject, "iss": issuer, "aud": audience, "iat": now, "nbf": now,
         "exp": now + timedelta(seconds=max(60, min(ttl_seconds, 3600))),
         "jti": uuid4().hex, "scope": " ".join(scopes)},
        key,
        algorithm="HS256",
    )


def _bearer_identity(request: Request) -> Optional[CurrentUser]:
    authorization = request.headers.get("Authorization", "")
    if not authorization:
        return None
    parts = authorization.split()
    if len(parts) != 2 or parts[0].lower() != "bearer" or len(parts[1]) > 8192:
        return None
    config = _jwt_configuration()
    if config is None:
        return None
    key, issuer, audience = config
    try:
        claims = jwt.decode(
            parts[1], key, algorithms=["HS256"], issuer=issuer, audience=audience,
            options={"require": ["sub", "iss", "aud", "iat", "nbf", "exp", "jti"]},
        )
    except jwt.PyJWTError:
        return None
    subject = _validated_subject(claims.get("sub"))
    if subject is None:
        return None
    scope = claims.get("scope", "")
    if not isinstance(scope, str):
        return None
    return CurrentUser(subject=subject, auth_source="server_context", scopes=tuple(scope.split()))


def get_optional_current_user(request: Request) -> Optional[CurrentUser]:
    """Return identity from server context, or explicit local-development header."""
    identity = _server_owned_identity(request)
    if identity is not None:
        return identity

    if request.headers.get("Authorization"):
        return _bearer_identity(request)

    if auth_mode() == "development":
        subject = _validated_subject(request.headers.get("X-Dev-User-Id"))
        if subject:
            return CurrentUser(subject=subject, auth_source="development_header")
    return None


def get_current_user(request: Request) -> CurrentUser:
    identity = get_optional_current_user(request)
    if identity is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication is required",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return identity


def require_corpus_admin(current_user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
    if os.getenv("ENABLE_CORPUS_ADMIN_API", "false").lower() not in {"true", "1"}:
        raise HTTPException(status_code=404, detail="Not found")
    if current_user.auth_source != "server_context" or "corpus:write" not in current_user.scopes:
        raise HTTPException(status_code=403, detail="Không có quyền quản trị kho tri thức")
    return current_user


def require_legacy_user_match(user_id: str, current_user: CurrentUser) -> None:
    """Allow legacy path-user endpoints only in explicitly enabled local mode."""
    legacy_enabled = os.getenv("ENABLE_LEGACY_USER_ENDPOINTS", "false").strip().lower()
    if auth_mode() != "development" or legacy_enabled not in {"1", "true", "yes", "on"}:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    if current_user.subject != user_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")


def personalization_debug_enabled() -> bool:
    value = os.getenv("ENABLE_PERSONALIZATION_DEBUG", "false").strip().lower()
    return auth_mode() == "development" and value in {"1", "true", "yes", "on"}
