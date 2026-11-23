"""A dispatch table is sufficient; no abstract factory hierarchy needed."""

from collections.abc import Callable


def lower(text: str) -> str:
    return text.lower().strip()


def upper(text: str) -> str:
    return text.upper().strip()


NORMALIZERS: dict[str, Callable[[str], str]] = {"lower": lower, "upper": upper}


def normalize(text: str, method: str) -> str:
    try:
        normalizer = NORMALIZERS[method]
    except KeyError as exc:
        raise ValueError(f"Unknown normalization method: {method}") from exc
    return normalizer(text)


if __name__ == "__main__":
    assert normalize(" Hello ", "lower") == "hello"
