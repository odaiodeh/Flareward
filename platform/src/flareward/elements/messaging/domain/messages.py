from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class Role(StrEnum):
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"
    TOOL = "tool"


class ToolCall(BaseModel):
    """Minimal representation of a tool call."""

    name: str
    args: dict[str, Any]
    tool_call_id: str

    model_config = ConfigDict(frozen=True)


class ChatMessage(BaseModel):
    """Immutable message with optional tool call or tool result."""

    role: Role
    content: str
    tool_calls: list[ToolCall] | None = None
    tool_call_id: str | None = None
    additional_kwargs: dict[str, Any] | None = None
    sender_id: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(frozen=True)

    @property
    def is_cancelled(self) -> bool:
        """Check if this message has been marked as cancelled."""
        return bool(self.metadata.get("is_cancelled"))
