"""One chat path shared by HTTP and Celery; clients cannot supply history."""
import logging
from typing import Any, Optional
from uuid import uuid4
from agents import multi_agent_handle
from agents.constants import AGENT_MAX_REQUEST_TIMEOUT_SECONDS, AGENT_REQUEST_TIMEOUT_SECONDS
from harness.budget import RequestBudget, call_with_supported_kwargs
from health.tools import check_medical_safety
from health.validation import validate_health_input
from persistence import personalization_service as profiles
from memory import store

logger = logging.getLogger(__name__)


def _degrade(response: dict, code: str, limitation: str) -> None:
    response["status"] = "degraded"
    response["errors"] = list(response.get("errors") or []) + [code]
    response["limitations"] = list(response.get("limitations") or []) + [limitation]


def _timeout_response(
    request_id: str,
    conversation_id: Optional[str],
    memory_status: str,
    safety: dict,
    context: dict,
) -> dict:
    chunks = [
        "Mình chưa thể hoàn tất phần diễn giải tự động trong thời gian cho phép."
    ]
    if safety:
        chunks.append("Lưu ý an toàn: {}".format(safety.get("disclaimer", "Thông tin chỉ mang tính tham khảo.")))
        if safety.get("risk_level") in {"urgent", "medical_caution"}:
            chunks.append(safety.get("recommended_action", "Nên tham khảo chuyên gia y tế khi cần."))
    return {
        "role": "assistant",
        "content": "\n\n".join(chunks),
        "status": "degraded",
        "fast_path": None,
        "agent_trace": [],
        "selected_agents": [],
        "selected_capabilities": [],
        "tool_results": [],
        "retrieved_docs": [],
        "evidence": [],
        "claim_evidence_links": [],
        "evidence_status": "insufficient",
        "limitations": ["Yêu cầu vượt quá ngân sách thời gian trước khi xử lý hoàn tất."],
        "safety_result": safety,
        "personalization_used": {
            "available": bool((context or {}).get("available")),
            "reason": (context or {}).get("reason"),
            "provenance": (context or {}).get("provenance") or [],
        },
        "errors": ["Request deadline exhausted"],
        "request_id": request_id,
        "conversation_id": conversation_id,
        "memory_status": memory_status,
        "memory_proposals": [],
    }


def _profile_conditions(context: dict) -> list:
    profile = (context or {}).get("profile") or {}
    conditions = profile.get("medical_conditions")
    if not conditions:
        return []
    if isinstance(conditions, list):
        return [str(item) for item in conditions if str(item).strip()]
    return [item.strip() for item in str(conditions).split(",") if item.strip()]


def run_chat(
    question: str,
    subject: str,
    conversation_id=None,
    *,
    bot_id="health-inbody-agent",
    deadline_monotonic: Optional[float] = None,
    cancel_event: Any = None,
) -> dict:
    request_id = f"req-{uuid4().hex[:12]}"
    # Emergency response must not wait for session storage or rate limits.
    if check_medical_safety(question).get("risk_level") == "urgent":
        response = multi_agent_handle(question, user_id=subject)
        response.update(request_id=request_id, conversation_id=None, memory_status="skipped_urgent")
        return response

    budget = (
        RequestBudget.start(
            AGENT_REQUEST_TIMEOUT_SECONDS,
            max_timeout_seconds=AGENT_MAX_REQUEST_TIMEOUT_SECONDS,
        )
        if deadline_monotonic is None
        else RequestBudget.from_deadline(
            deadline_monotonic,
            max_timeout_seconds=AGENT_MAX_REQUEST_TIMEOUT_SECONDS,
        )
    )
    validate_health_input(question)
    context = profiles.safe_build_confirmed_context(subject)
    history, memory_status = [], "disabled"
    if conversation_id:
        history = store.load_history(subject, str(conversation_id))
        memory_status = "active"
    elif context.get("available"):
        try:
            conversation_id = store.open_conversation(subject, bot_id)["conversation_id"]
            memory_status = "active"
        except Exception as exc:
            logger.warning("Chat session creation failed (%s)", type(exc).__name__)
            # Consent may have changed since the context read. Do not use the
            # snapshot when its ownership/consent cannot be rechecked.
            context = {"available": False, "reason": "personalization_temporarily_unavailable", "provenance": []}
            memory_status = "unavailable"

    cancelled = bool(cancel_event is not None and cancel_event.is_set())
    if cancelled or budget.exhausted():
        safety = check_medical_safety(question, _profile_conditions(context))
        return _timeout_response(
            request_id=request_id,
            conversation_id=str(conversation_id) if conversation_id else None,
            memory_status=memory_status,
            safety=safety,
            context=context,
        )

    response = call_with_supported_kwargs(
        multi_agent_handle,
        question,
        history=history,
        user_id=subject,
        user_profile=context,
        conversation_id=str(conversation_id or "main"),
        deadline_monotonic=budget.deadline_monotonic,
        cancel_event=cancel_event,
    )
    response.update(request_id=request_id,
                    conversation_id=str(conversation_id) if conversation_id else None, memory_status=memory_status,
                    memory_proposals=[])
    if memory_status == "unavailable":
        _degrade(response, "conversation_storage_unavailable", "Không thể tạo phiên hội thoại; lượt này chưa được lưu.")
    if conversation_id and not (cancel_event is not None and cancel_event.is_set()):
        try:
            turn = store.record_turn(subject, str(conversation_id), question, response["content"])
            response["user_message_id"] = turn["user_message_id"]
        except Exception as exc:
            logger.warning("Chat memory write failed (%s)", type(exc).__name__)
            response["memory_status"] = "write_unavailable"
            _degrade(response, "conversation_write_unavailable", "Lượt này chưa được lưu đầy đủ vào bộ nhớ.")
        else:
            if (
                (response.get("safety_result") or {}).get("risk_level") == "low"
                and not budget.exhausted(min_required=0.2)
            ):
                try:
                    response["memory_proposals"] = store.propose_from_turn(subject, turn["user_message_id"], question)
                except Exception as exc:
                    logger.warning("Chat memory proposal failed (%s)", type(exc).__name__)
                    _degrade(response, "memory_proposal_unavailable", "Chưa thể tạo gợi ý ghi nhớ cho lượt này.")
    return response
