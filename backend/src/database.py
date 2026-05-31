"""Database connection/session helpers for Health/InBody backend."""
import os
from contextlib import contextmanager

from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

DEFAULT_DATABASE_URL = (
    "postgresql+psycopg2://health_user:health_password@postgres-db:5432/health_inbody"
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

    broker_url = os.environ.get("CELERY_BROKER_URL", "redis://valkey-db:6379/0")
    result_backend = os.environ.get("CELERY_RESULT_BACKEND", broker_url)
    return Celery(name, broker=broker_url, backend=result_backend)
