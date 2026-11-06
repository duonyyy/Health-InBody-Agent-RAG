"""First-party username/password enrollment and short-lived JWT issuance."""

import re
from uuid import uuid4

from argon2 import PasswordHasher, Type
from argon2.exceptions import InvalidHashError, VerifyMismatchError
from sqlalchemy.exc import IntegrityError

from auth.context import _jwt_configuration, issue_access_token
from persistence.database import session_scope
from persistence.models import AuthCredential, User


_USERNAME = re.compile(r"^[a-z0-9][a-z0-9._-]{2,39}$")
_HASHER = PasswordHasher(time_cost=2, memory_cost=19456, parallelism=1, type=Type.ID)


class AccountConflict(Exception):
    pass


class InvalidCredentials(Exception):
    pass


def _normalized_username(username: str) -> str:
    value = username.strip().lower()
    if not _USERNAME.fullmatch(value):
        raise ValueError("Tên đăng nhập phải có 3–40 ký tự chữ thường, số, dấu chấm, gạch dưới hoặc gạch ngang.")
    return value


def register_account(username: str, password: str) -> dict:
    if _jwt_configuration() is None:
        raise RuntimeError("JWT chưa được cấu hình")
    normalized = _normalized_username(username)
    if len(password) < 12 or len(password) > 128:
        raise ValueError("Mật khẩu phải có 12–128 ký tự.")
    password_hash = _HASHER.hash(password)
    subject = "bw_" + uuid4().hex
    try:
        with session_scope() as db:
            user = User(external_id=subject, consent_flags={"health_data_processing": False, "personalization": False})
            db.add(user)
            db.flush()
            db.add(AuthCredential(user_id=user.id, username=normalized, password_hash=password_hash))
    except IntegrityError as exc:
        raise AccountConflict() from exc
    return {"access_token": issue_access_token(subject), "token_type": "bearer", "expires_in": 900}


def login_account(username: str, password: str) -> dict:
    if _jwt_configuration() is None:
        raise RuntimeError("JWT chưa được cấu hình")
    try:
        normalized = _normalized_username(username)
    except ValueError as exc:
        raise InvalidCredentials() from exc
    with session_scope() as db:
        row = db.query(AuthCredential, User).join(User, AuthCredential.user_id == User.id).filter(
            AuthCredential.username == normalized,
            AuthCredential.active.is_(True),
            User.deleted_at.is_(None),
        ).first()
        if row is None:
            raise InvalidCredentials()
        credential, user = row
        try:
            valid = _HASHER.verify(credential.password_hash, password)
        except (VerifyMismatchError, InvalidHashError) as exc:
            raise InvalidCredentials() from exc
        if not valid:
            raise InvalidCredentials()
        subject = user.external_id
    return {"access_token": issue_access_token(subject), "token_type": "bearer", "expires_in": 900}
