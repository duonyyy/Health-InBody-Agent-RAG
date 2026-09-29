"""Deterministic call-count and time-reserve decision."""


def reserve_allows_call(*, remaining_seconds: float, reserve_seconds: float,
                        used: int, maximum: int) -> bool:
    return (used < maximum and maximum > 0
            and remaining_seconds > max(0.0, reserve_seconds))
