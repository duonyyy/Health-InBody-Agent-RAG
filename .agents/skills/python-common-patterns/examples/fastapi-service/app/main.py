"""Small example app. Do not copy demo bootstrap into production unchanged."""

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from .db import init_demo_database
from .errors import TaskNotFound
from .router import router

init_demo_database()
app = FastAPI(title="Common Patterns FastAPI Example")
app.include_router(router)


@app.exception_handler(TaskNotFound)
async def task_not_found_handler(_request: Request, exc: TaskNotFound) -> JSONResponse:
    return JSONResponse(status_code=404, content={"code": "TASK_NOT_FOUND", "detail": str(exc)})
