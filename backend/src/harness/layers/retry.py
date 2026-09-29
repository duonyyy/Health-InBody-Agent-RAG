"""Recognize degraded tool observations even when an adapter reports ok=True."""

from typing import Any

from harness.budget import retryable_llm_error


_DEGRADED_PREFIXES = ("[TRUNCATED:", "[NOISE:", "[TOOL_ERROR]", "timeout:")


def degraded_observation(result: Any) -> bool:
    if isinstance(result, list):
        return any(degraded_observation(item) for item in result)
    if isinstance(result, dict):
        if result.get("truncated") is True or result.get("ok") is False:
            return True
        content = str(result.get("content") or result.get("page_content") or "")
    else:
        content = str(result or "")
    return content.lstrip().startswith(_DEGRADED_PREFIXES)


__all__ = ["degraded_observation", "retryable_llm_error"]
