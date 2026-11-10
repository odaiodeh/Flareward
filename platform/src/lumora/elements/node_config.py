"""Portable node configuration and narrowly scoped legacy normalization."""

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class NodeBaseConfig(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        arbitrary_types_allowed=True,
        hide_input_in_errors=True,
    )
    retries: int | None = Field(default=1, description="Retry count if failure")


def retired_sandbox_configuration(value: Any) -> Any:
    """Accept an old unused null default; never discard requested isolation."""
    if not isinstance(value, dict) or "sandbox" not in value:
        return value
    if value["sandbox"] is not None:
        raise ValueError("Agent sandbox elements are retired; select an execution profile")
    return {key: item for key, item in value.items() if key != "sandbox"}
