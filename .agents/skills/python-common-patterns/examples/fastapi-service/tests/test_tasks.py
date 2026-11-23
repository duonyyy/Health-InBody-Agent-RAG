from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.db import get_session
from app.main import app
from app.models import Base, TaskModel
from app.repository import TaskRepository
from app.service import TaskService


@pytest.fixture
def db_session_factory():
    # StaticPool keeps the same SQLite in-memory connection across threads.
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    try:
        yield factory
    finally:
        engine.dispose()


@pytest.fixture
def client(db_session_factory) -> Iterator[TestClient]:
    def override_session() -> Iterator[Session]:
        with db_session_factory() as session:
            yield session

    app.dependency_overrides[get_session] = override_session
    try:
        with TestClient(app) as test_client:
            yield test_client
    finally:
        app.dependency_overrides.clear()


def test_create_get_and_complete_task(client: TestClient):
    response = client.post("/tasks", json={"title": "Review PR"})
    assert response.status_code == 201
    created = response.json()
    assert created["title"] == "Review PR"
    assert created["completed"] is False

    response = client.get(f"/tasks/{created['id']}")
    assert response.status_code == 200
    assert response.json() == created

    completed = client.post(f"/tasks/{created['id']}/complete")
    assert completed.status_code == 200
    assert completed.json()["completed"] is True


def test_not_found_maps_to_404(client: TestClient):
    response = client.get("/tasks/999")
    assert response.status_code == 404
    assert response.json()["code"] == "TASK_NOT_FOUND"
    assert client.post("/tasks/999/complete").status_code == 404


def test_validation_error_is_422(client: TestClient):
    response = client.post("/tasks", json={"title": ""})
    assert response.status_code == 422


def test_transaction_rolls_back_when_repository_fails(db_session_factory):
    class ExplodingRepository(TaskRepository):
        def add(self, title: str) -> TaskModel:
            super().add(title)  # flush writes within current transaction
            raise RuntimeError("simulated failure before commit")

    with db_session_factory() as session:
        service = TaskService(session, ExplodingRepository(session))
        with pytest.raises(RuntimeError, match="simulated failure"):
            service.create("must be rolled back")

    with db_session_factory() as session:
        assert session.scalars(select(TaskModel)).all() == []
