"""Public first-party sign-in endpoints; identity is never accepted from a client field."""

import hashlib

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from auth.accounts import AccountConflict, InvalidCredentials, login_account, register_account
from auth.context import auth_mode
from core.cache import get_redis_client


router = APIRouter(prefix="/auth", tags=["auth"])


class Credentials(BaseModel):
    username: str = Field(min_length=3, max_length=40)
    password: str = Field(min_length=12, max_length=128)


def _require_production_mode() -> None:
    if auth_mode() != "production":
        raise HTTPException(status_code=404, detail="Not found")


def _rate_limit(request: Request, username: str) -> None:
    """Shared fixed-window limit; fail closed when the production store is offline."""
    client = get_redis_client()
    if client is None:
        raise HTTPException(status_code=503, detail="Đăng nhập tạm thời không khả dụng.")
    peer = request.client.host if request.client else "unknown"
    normalized = username.strip().lower()
    identifiers = (
        (f"pair:{peer}|{normalized}", 5),
        (f"ip:{peer}", 30),
        (f"username:{normalized}", 15),
    )
    try:
        counts = []
        for identifier, limit in identifiers:
            key = "bodywise:auth:attempts:" + hashlib.sha256(identifier.encode()).hexdigest()
            count = client.incr(key)
            if count == 1:
                client.expire(key, 60)
            counts.append((count, limit))
    except Exception as exc:
        raise HTTPException(status_code=503, detail="Đăng nhập tạm thời không khả dụng.") from exc
    if any(count > limit for count, limit in counts):
        raise HTTPException(status_code=429, detail="Thử đăng nhập quá nhiều lần. Vui lòng chờ một phút.")


@router.post("/register", status_code=201)
def register(data: Credentials, request: Request):
    _require_production_mode()
    _rate_limit(request, data.username)
    try:
        return register_account(data.username, data.password)
    except AccountConflict as exc:
        raise HTTPException(status_code=409, detail="Tên đăng nhập đã tồn tại.") from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail="Đăng nhập chưa được cấu hình.") from exc


@router.post("/login")
def login(data: Credentials, request: Request):
    _require_production_mode()
    _rate_limit(request, data.username)
    try:
        return login_account(data.username, data.password)
    except InvalidCredentials as exc:
        raise HTTPException(status_code=401, detail="Tên đăng nhập hoặc mật khẩu không đúng.") from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail="Đăng nhập chưa được cấu hình.") from exc
