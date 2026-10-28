"""Question normalizer agent: resolves follow-up conversational questions."""

import logging

from llm.client import detect_user_intent
from ..state import AgentState, append_error, append_trace

logger = logging.getLogger(__name__)


def normalize_question_agent(state: AgentState) -> AgentState:
    question = state.get("question") or ""
    history = state.get("history") or []
    try:
        standalone = detect_user_intent(history, question)
        state["standalone_question"] = standalone or question
        append_trace(
            state,
            "QuestionNormalizerAgent",
            "normalize_follow_up_question",
            "success",
            "Prepared standalone question from conversation history.",
        )
    except Exception as exc:
        logger.warning("Question normalization failed: %s", exc)
        state["standalone_question"] = question
        append_error(state, "Question normalization is temporarily unavailable")
        append_trace(
            state,
            "QuestionNormalizerAgent",
            "normalize_follow_up_question",
            "warning",
            "Used original question because normalization failed.",
        )
    return state
