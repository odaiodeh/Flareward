"""Strict frozen boundary values shared by domain and application contracts."""

from pydantic import BaseModel, ConfigDict


class Model(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
