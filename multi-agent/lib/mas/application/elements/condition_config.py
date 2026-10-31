"""Validated condition configuration, independent of concrete plugin schemas."""

from pydantic import BaseModel, ConfigDict


class BaseConditionConfig(BaseModel):
    model_config = ConfigDict(extra="forbid", hide_input_in_errors=True)
