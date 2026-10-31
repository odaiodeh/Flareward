"""Shared public settings for authoring probes."""

from pydantic import AliasChoices, BaseModel, ConfigDict, Field


class ValidationSettings(BaseModel):
    model_config = ConfigDict(extra="forbid")
    timeout_seconds: float = Field(
        default=10,
        gt=0,
        le=60,
        allow_inf_nan=False,
        validation_alias=AliasChoices("timeout_seconds", "timeoutSeconds"),
    )
