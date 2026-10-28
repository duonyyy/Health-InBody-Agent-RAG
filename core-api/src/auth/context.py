"""Resolve authenticated identity without trusting client-supplied user IDs."""

import os
import re
from dataclasses import dataclass
from typing import Any, Optional

from fastapi import Depends, HTTPException, Request, status


_SUBJECT_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:@-]{0,127}$")


@dataclass(frozen=True)
class CurrentUser:
    """Minimal server-owned identity passed into ownership-scoped services."""

    subject: str
    auth_source: str = "server_context"
    scopes: tuple[str, ...] = ()


def auth_mode() -> str:
    return os.getenv("AUTH_MODE", "development").strip().lower()


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


def get_optional_current_user(request: Request) -> Optional[CurrentUser]:
    """Return identity from server context, or explicit local-development header."""
    identity = _server_owned_identity(request)
    if identity is not None:
        return identity

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
