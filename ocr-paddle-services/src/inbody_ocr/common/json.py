"""Only the JSON extraction needed by InBody OCR."""

import json
from typing import Any


class JsonExtractionError(ValueError):
    pass


def extract_json_object(text: str) -> dict[str, Any]:
    candidate = text.strip()
    if candidate.startswith("```"):
        lines = candidate.splitlines()
        candidate = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])
    try:
        value = json.loads(candidate)
    except (json.JSONDecodeError, TypeError) as exc:
        raise JsonExtractionError("Model did not return one JSON object") from exc
    if not isinstance(value, dict):
        raise JsonExtractionError("Model did not return a JSON object")
    return value
