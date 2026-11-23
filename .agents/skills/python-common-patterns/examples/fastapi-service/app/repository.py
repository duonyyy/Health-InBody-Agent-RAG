"""Repository maps DB access; never commits/rollbacks or raises HTTP errors."""

from sqlalchemy.orm import Session

from .models import TaskModel


class TaskRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get(self, task_id: int) -> TaskModel | None:
        return self.session.get(TaskModel, task_id)

    def add(self, title: str) -> TaskModel:
        task = TaskModel(title=title, completed=False)
        self.session.add(task)
        self.session.flush()  # get auto ID, NOT commit
        return task
