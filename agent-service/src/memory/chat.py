"""One chat path shared by HTTP and Celery; clients cannot supply history."""
import logging
from agents import multi_agent_handle
from health.tools import check_medical_safety
from persistence import personalization_service as profiles
from memory import store

logger = logging.getLogger(__name__)


def run_chat(question: str, subject: str, conversation_id=None, *, bot_id="health-inbody-agent",
             use_zep_memory=False) -> dict:
    # Emergency response must not wait for session storage or a remote memory call.
    if check_medical_safety(question).get("risk_level") == "urgent":
        response = multi_agent_handle(question, user_id=subject)
        response.update(conversation_id=None, memory_status="skipped_urgent")
        return response
    context = profiles.safe_build_confirmed_context(subject)
    history, memory_status = [], "disabled"
    if conversation_id:
        history = store.load_history(subject, str(conversation_id))
        memory_status = "active"
    elif context.get("available"):
        conversation_id = store.open_conversation(subject, bot_id)["conversation_id"]
        memory_status = "active"
    response = multi_agent_handle(question, history=history, user_id=subject, user_profile=context,
                                  use_zep_memory=use_zep_memory, conversation_id=str(conversation_id or "main"))
    response.update(conversation_id=str(conversation_id) if conversation_id else None, memory_status=memory_status,
                    memory_proposals=[])
    if conversation_id:
        try:
            turn = store.record_turn(subject, str(conversation_id), question, response["content"])
            response["user_message_id"] = turn["user_message_id"]
            if (response.get("safety_result") or {}).get("risk_level") == "low":
                response["memory_proposals"] = store.propose_from_turn(subject, turn["user_message_id"], question)
        except Exception as exc:
            logger.warning("Chat memory write failed (%s)", type(exc).__name__)
            response["memory_status"] = "write_unavailable"
            response["limitations"] = list(response.get("limitations") or []) + ["Lượt này chưa được lưu đầy đủ vào bộ nhớ."]
    return response
