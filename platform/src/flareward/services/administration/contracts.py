"""Portable configuration sections and optimistic editing contracts."""

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from pydantic import BaseModel, ConfigDict, Field, JsonValue


class SettingsUnavailable(RuntimeError):
    pass


class SettingsConflict(ValueError):
    pass


class SettingsRecord(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    key: str
    value: dict[str, JsonValue]
    revision: int = Field(ge=1)
    updated_at: datetime


class SettingsRepository(Protocol):
    async def get(self, key: str) -> SettingsRecord | None: ...
    async def replace(self, record: SettingsRecord, expected_revision: int) -> bool: ...


@dataclass(frozen=True)
class SettingsSection:
    key: str
    category: str
    title: str
    schema: type[BaseModel]
    defaults: dict[str, JsonValue]
