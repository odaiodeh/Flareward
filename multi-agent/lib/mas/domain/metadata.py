"""Portable presentation metadata shared by authored execution steps."""

from pydantic import BaseModel, ConfigDict, Field


class StepMeta(BaseModel):
    model_config = ConfigDict(extra="forbid")
    description: str = ""
    display_name: str = ""
    tags: list[str] = Field(default_factory=list)
