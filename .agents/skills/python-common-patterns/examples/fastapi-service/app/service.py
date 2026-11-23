"""Application service owns writes and transaction boundaries."""

from sqlalchemy.orm import Session

from .errors import TaskNotFound
from .repository import TaskRepository
from .schemas import TaskRead


class TaskService:
    def __init__(self, session: Session, repository: TaskRepository) -> None:
        self.session = session
        self.repository = repository

    def create(self, title: str) -> TaskRead:
        # Session must not have an open transaction when entering begin().
        with self.session.begin():
            task = self.repository.add(title)
            result = TaskRead.model_validate(task)
        return result  # transaction committed after context exits

    def get(self, task_id: int) -> TaskRead:
        task = self.repository.get(task_id)
        if task is None:
            raise TaskNotFound(task_id)
        return TaskRead.model_validate(task)

    def complete(self, task_id: int) -> TaskRead:
        with self.session.begin():
            task = self.repository.get(task_id)
            if task is None:
                raise TaskNotFound(task_id)  # auto rollback
            task.completed = True
            self.session.flush()
            result = TaskRead.model_validate(task)
        return result
