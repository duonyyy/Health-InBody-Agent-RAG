"""Domain exception; does not depend on HTTP or FastAPI."""


class TaskNotFound(Exception):
    def __init__(self, task_id: int) -> None:
        super().__init__(f"Task {task_id} not found")
        self.task_id = task_id
