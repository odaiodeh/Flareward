from pydantic import JsonValue


def derive_title(inputs: dict[str, JsonValue], max_chars: int = 40) -> str | None:
    """
    Returns the first non-empty user prompt clipped to `max_chars`.
    """
    prompt = inputs.get("user_prompt") or next(
        (value for value in inputs.values() if isinstance(value, str)), ""
    )
    if not isinstance(prompt, str):
        return None
    prompt = prompt.strip()
    return (prompt[:max_chars] + "…") if len(prompt) > max_chars else (prompt or None)
