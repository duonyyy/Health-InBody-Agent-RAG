"""HTTP boundary: Depends / status code / schemas, but no SQL and no commits."""

from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from .db import get_session
from .repository import TaskRepository
from .schemas import TaskCreate, TaskRead
from .service import TaskService

router = APIRouter(prefix="/tasks", tags=["tasks"])
SessionDep = Annotated[Session, Depends(get_session)]


def build_service(session: Session) -> TaskService:
    return TaskService(session=session, repository=TaskRepository(session))


@router.post("", response_model=TaskRead, status_code=status.HTTP_201_CREATED)
def create_task(body: TaskCreate, session: SessionDep) -> TaskRead:
    return build_service(session).create(body.title)


@router.get("/{task_id}", response_model=TaskRead)
def get_task(task_id: int, session: SessionDep) -> TaskRead:
    return build_service(session).get(task_id)


@router.post("/{task_id}/complete", response_model=TaskRead)
def complete_task(task_id: int, session: SessionDep) -> TaskRead:
    return build_service(session).complete(task_id)
