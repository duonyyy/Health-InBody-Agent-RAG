"""Database connection/session helpers for Health/InBody backend."""
import os
from contextlib import contextmanager

from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

from core.config import (
    DEFAULT_CELERY_BROKER_URL,
    DEFAULT_CELERY_RESULT_BACKEND,
    DEFAULT_DATABASE_URL,
)

DATABASE_URL = os.environ.get("DATABASE_URL", DEFAULT_DATABASE_URL)

_engine_options = {"pool_pre_ping": True}
if not DATABASE_URL.startswith("sqlite"):
    _engine_options.update(
        pool_size=int(os.environ.get("DB_POOL_SIZE", "5")),
        max_overflow=int(os.environ.get("DB_MAX_OVERFLOW", "10")),
        pool_timeout=float(os.environ.get("DB_POOL_TIMEOUT_SECONDS", "5")),
    )
    if DATABASE_URL.startswith("postgresql"):
        _connect_timeout = max(1, int(os.environ.get("DB_CONNECT_TIMEOUT_SECONDS", "5")))
        _statement_timeout_ms = max(1000, int(os.environ.get("DB_STATEMENT_TIMEOUT_MS", "10000")))
        _engine_options["connect_args"] = {
            "connect_timeout": _connect_timeout,
            "options": f"-c statement_timeout={_statement_timeout_ms}",
        }

engine = create_engine(DATABASE_URL, **_engine_options)

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
)

Base = declarative_base()


def get_db():
    """FastAPI dependency that yields a SQLAlchemy session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@contextmanager
def session_scope():
    """Context manager for scripts/tasks."""
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def init_db():
    """Create ORM tables if they do not exist."""
    import persistence.models  # noqa: F401
    import memory.models  # noqa: F401

    Base.metadata.create_all(bind=engine)


def get_celery_app(name="health_inbody_tasks"):
    """
    Backward-compatible Celery factory.

    New code in tasks.py creates celery_app directly, but this helper is kept for
    older imports.
    """
    from celery import Celery

    return Celery(
        name,
        broker=DEFAULT_CELERY_BROKER_URL,
        backend=DEFAULT_CELERY_RESULT_BACKEND,
    )
