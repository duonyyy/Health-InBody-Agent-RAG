"""Bounded retry for transient synchronous calls with safe/idempotent semantics.

This intentionally does NOT retry arbitrary Exception, business errors, or writes
without durable idempotency. Use asyncio.sleep in asynchronous code.
"""

import random
import time
from collections.abc import Callable
from typing import TypeVar

T = TypeVar("T")


def with_retry(call: Callable[[], T], attempts: int = 3, base_delay: float = 0.1) -> T:
    if attempts < 1 or base_delay < 0:
        raise ValueError("invalid retry policy")
    for i in range(attempts):
        try:
            return call()
        except (TimeoutError, ConnectionError):
            if i == attempts - 1:
                raise
            delay = min(2.0, base_delay * 2**i) * random.uniform(0.5, 1.5)
            time.sleep(delay)
    raise AssertionError("unreachable")
