from uuid import uuid4

from flareward.elements.messaging.domain.messages import ToolCall


def ensure_tool_call_id(data: dict) -> ToolCall:
    """Return a ToolCall with a guaranteed non-empty id."""
    return ToolCall(
        name=data["name"], args=data["args"], tool_call_id=data.get("id") or f"tool-{uuid4()}"
    )
