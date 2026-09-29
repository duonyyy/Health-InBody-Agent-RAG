"""Bounded retry policy shared by agent calls; no patient payload logging."""


def retryable_llm_error(exc: Exception) -> bool:
    if isinstance(exc, (TimeoutError, ConnectionError)):
        return True
    message = str(exc).lower()
    return any(token in message for token in (" 429", " 502", " 503", " 504", "timed out", "truncated"))
