"""Unit tests for ChatService application layer.

Validates (python-common-patterns references/service-layer.md):
- ChatService domain logic executed independently without HTTP layer/TestClient.
- Correct domain exceptions: QueueUnavailableError, CeleryBackendUnavailableError, TaskExecutionFailedError.
- Synchronous chat, asynchronous dispatch, task polling, and agent answer formatting.
"""

import asyncio
import os
from types import SimpleNamespace
import pytest

os.environ.setdefault("DATABASE_URL", "sqlite://")

from services.chat_service import (
    CeleryBackendUnavailableError,
    ChatPollResult,
    ChatService,
    QueueUnavailableError,
    TaskExecutionFailedError,
    format_agent_response,
)


def test_chat_service_sync_urgent_bypasses_lane():
    called = []

    def fake_chat(question, subject, **kw):
        called.append((question, subject))
        return {"content": "Cấp cứu ngay", "status": "ok", "fast_path": "urgent_safety"}

    service = ChatService(chat_fn=fake_chat)
    result = asyncio.run(service.execute_sync_chat("đau ngực dữ dội khó thở", "alice", urgent=True))

    assert result["content"] == "Cấp cứu ngay"
    assert result["fast_path"] == "urgent_safety"
    assert called == [("đau ngực dữ dội khó thở", "alice")]


def test_chat_service_dispatch_async_raises_when_queue_missing():
    service = ChatService(llm_handler=object())  # object() has no apply_async

    with pytest.raises(QueueUnavailableError, match="Hàng đợi hội thoại hiện không khả dụng"):
        asyncio.run(service.dispatch_async_chat("câu hỏi", "alice"))


def test_chat_service_dispatch_async_success():
    dispatched = []

    class FakeLlmHandler:
        def apply_async(self, args, task_id, expires, kwargs, **kw):
            dispatched.append({"args": args, "task_id": task_id, "expires": expires})

    fake_store = SimpleNamespace(
        create_task=lambda subject, **kw: "custom-task-uuid-123",
        load_history=lambda subject, conv_id, **kw: [],
    )

    service = ChatService(
        store=fake_store,
        llm_handler=FakeLlmHandler(),
    )
    task_id = asyncio.run(service.dispatch_async_chat("câu hỏi", "alice", conversation_id="conv-1"))

    assert task_id == "custom-task-uuid-123"
    assert len(dispatched) == 1
    assert dispatched[0]["task_id"] == "custom-task-uuid-123"
    assert dispatched[0]["args"][1] == "alice"
    assert dispatched[0]["args"][2] == "câu hỏi"


def test_chat_service_poll_raises_when_celery_backend_unavailable():
    fake_store = SimpleNamespace(
        require_task_owner=lambda subject, task_id, **kw: True,
    )
    service = ChatService(store=fake_store, async_result_cls=None)

    with pytest.raises(CeleryBackendUnavailableError):
        asyncio.run(service.poll_task_status("task-1", "alice"))


def test_chat_service_poll_returns_completed_result():
    class FakeAsyncResult:
        status = "SUCCESS"
        result = {"content": "Kết quả xử lý xong"}

        def __init__(self, task_id):
            self.task_id = task_id

    fake_store = SimpleNamespace(
        require_task_owner=lambda subject, task_id, **kw: True,
    )
    service = ChatService(store=fake_store, async_result_cls=FakeAsyncResult)

    poll_result = asyncio.run(service.poll_task_status("task-1", "alice", wait=False))

    assert poll_result.is_ready is True
    assert poll_result.status == "SUCCESS"
    assert poll_result.result == {"content": "Kết quả xử lý xong"}


def test_chat_service_poll_raises_on_task_failure():
    class FakeFailedAsyncResult:
        status = "FAILURE"
        result = None

        def __init__(self, task_id):
            self.task_id = task_id

    fake_store = SimpleNamespace(
        require_task_owner=lambda subject, task_id, **kw: True,
    )
    service = ChatService(store=fake_store, async_result_cls=FakeFailedAsyncResult)

    with pytest.raises(TaskExecutionFailedError):
        asyncio.run(service.poll_task_status("task-1", "alice", wait=False))


def test_format_agent_response():
    raw = {
        "content": "Lời khuyên dinh dưỡng.",
        "request_id": "req-1",
        "conversation_id": "conv-1",
        "status": "ok",
        "evidence": [{"source": "doc-1"}],
    }
    formatted = format_agent_response(raw, request_started=0.0)

    assert formatted["answer"] == "Lời khuyên dinh dưỡng."
    assert formatted["request_id"] == "req-1"
    assert formatted["citations"] == [{"source": "doc-1"}]
    assert "latency_ms" in formatted
    assert "agent" in formatted
