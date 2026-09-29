"""Authentication context boundary for Health/InBody APIs."""

from .context import (
    CurrentUser,
    get_current_user,
    get_optional_current_user,
    require_legacy_user_match,
)

__all__ = [
    "CurrentUser",
    "get_current_user",
    "get_optional_current_user",
    "require_legacy_user_match",
]
