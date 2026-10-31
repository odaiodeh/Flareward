"""Provider-agnostic tool schema — pure data, no execution logic."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, JsonValue


class ToolDefinition(BaseModel):
    """Provider-agnostic tool schema for LLM function-calling registration."""

    model_config = ConfigDict(frozen=True)

    name: str
    description: str = ""
    parameters: dict[str, JsonValue] = Field(
        default_factory=lambda: {"type": "object", "properties": {}}
    )
