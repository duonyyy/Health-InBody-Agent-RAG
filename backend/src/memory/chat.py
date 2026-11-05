"""One chat path shared by HTTP and Celery; clients cannot supply history."""
import logging
from uuid import uuid4
from agents import multi_agent_handle
from health.tools import check_medical_safety
from persistence import personalization_service as profiles
from memory import store

logger = logging.getLogger(__name__)


def _degrade(response: dict, code: str, limitation: str) -> None:
    response["status"] = "degraded"
    response["errors"] = list(response.get("errors") or []) + [code]
    response["limitations"] = list(response.get("limitations") or []) + [limitation]


def run_chat(question: str, subject: str, conversation_id=None, *, bot_id="health-inbody-agent",
             use_zep_memory=False) -> dict:
    request_id = f"req-{uuid4().hex[:12]}"
    # Emergency response must not wait for session storage or a remote memory call.
    if check_medical_safety(question).get("risk_level") == "urgent":
        response = multi_agent_handle(question, user_id=subject)
        response.update(request_id=request_id, conversation_id=None, memory_status="skipped_urgent")
        return response
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
    response = multi_agent_handle(question, history=history, user_id=subject, user_profile=context,
                                  use_zep_memory=use_zep_memory, conversation_id=str(conversation_id or "main"))
    response.update(request_id=request_id,
                    conversation_id=str(conversation_id) if conversation_id else None, memory_status=memory_status,
                    memory_proposals=[])
    if memory_status == "unavailable":
        _degrade(response, "conversation_storage_unavailable", "Không thể tạo phiên hội thoại; lượt này chưa được lưu.")
    if conversation_id:
        try:
            turn = store.record_turn(subject, str(conversation_id), question, response["content"])
            response["user_message_id"] = turn["user_message_id"]
        except Exception as exc:
            logger.warning("Chat memory write failed (%s)", type(exc).__name__)
            response["memory_status"] = "write_unavailable"
            _degrade(response, "conversation_write_unavailable", "Lượt này chưa được lưu đầy đủ vào bộ nhớ.")
        else:
            if (response.get("safety_result") or {}).get("risk_level") == "low":
                try:
                    response["memory_proposals"] = store.propose_from_turn(subject, turn["user_message_id"], question)
                except Exception as exc:
                    logger.warning("Chat memory proposal failed (%s)", type(exc).__name__)
                    _degrade(response, "memory_proposal_unavailable", "Chưa thể tạo gợi ý ghi nhớ cho lượt này.")
    return response
