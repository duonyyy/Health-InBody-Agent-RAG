"""DEMO ONLY: SQLite bootstrap and request-scoped session dependency."""

from collections.abc import Iterator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from .models import Base

engine = create_engine("sqlite:///./tasks.db", connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)


def init_demo_database() -> None:
    # Production: run migrations instead of create_all at import/startup.
    Base.metadata.create_all(engine)


def get_session() -> Iterator[Session]:
    with SessionLocal() as session:
        yield session
