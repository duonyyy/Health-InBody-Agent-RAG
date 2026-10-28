"""Pure context budget independent of database/provider availability."""


def bounded_history(messages: list[dict]) -> list[dict[str, str]]:
    result, remaining = [], 6000
    for item in reversed(messages[-10:]):
        if item.get("role") not in {"user", "assistant"}:
            continue
        content = str(item.get("content") or "")[:min(1500, remaining)]
        if not content:
            continue
        result.append({"role": item["role"], "content": content})
        remaining -= len(content)
        if remaining <= 0:
            break
    return list(reversed(result))
