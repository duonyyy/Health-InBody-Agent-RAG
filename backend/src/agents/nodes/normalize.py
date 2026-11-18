"""Question normalizer agent: resolves follow-up conversational questions."""

import logging

from harness.budget import call_with_supported_kwargs
from llm.client import LLM_NORMALIZE_TIMEOUT, detect_user_intent
from ..constants import AGENT_COMPOSER_RESERVE_SECONDS, AGENT_MIN_CALL_TIMEOUT_SECONDS
from ..context import _bounded_timeout, _deadline_monotonic, _is_cancelled
from ..state import AgentState, append_error, append_trace

logger = logging.getLogger(__name__)


def normalize_question_agent(state: AgentState) -> AgentState:
    question = state.get("question") or ""
    history = state.get("history") or []
    if not history:
        state["standalone_question"] = question
        append_trace(
            state,
            "QuestionNormalizerAgent",
            "normalize_follow_up_question",
            "success",
            "Prepared standalone question from conversation history.",
        )
        return state

    if _is_cancelled(state):
        state["standalone_question"] = question
        append_trace(
            state,
            "QuestionNormalizerAgent",
            "normalize_cancelled",
            "warning",
            "Skipped normalization because request was cancelled.",
        )
        return state

    norm_timeout = _bounded_timeout(
        state,
        LLM_NORMALIZE_TIMEOUT,
        reserve_seconds=AGENT_COMPOSER_RESERVE_SECONDS,
        min_timeout=AGENT_MIN_CALL_TIMEOUT_SECONDS,
    )
    if norm_timeout <= 0:
        state["standalone_question"] = question
        append_trace(
            state,
            "QuestionNormalizerAgent",
            "normalize_budget_skipped",
            "warning",
            "Skipped follow-up normalization to preserve remaining request budget.",
        )
        return state

    try:
        standalone = call_with_supported_kwargs(
            detect_user_intent,
            history,
            question,
            timeout=norm_timeout,
            deadline_monotonic=_deadline_monotonic(state),
        )
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
