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

engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
    pool_size=int(os.environ.get("DB_POOL_SIZE", "5")),
    max_overflow=int(os.environ.get("DB_MAX_OVERFLOW", "10")),
)

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
    import models  # noqa: F401

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
