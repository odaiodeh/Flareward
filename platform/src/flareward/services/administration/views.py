"""Schema-driven configuration views, separate from stored settings and authority."""

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, JsonValue


class FieldKind(StrEnum):
    STRING_LIST = "string_list"
    STRING = "string"
    BOOLEAN = "boolean"
    NUMBER = "number"
    JSON = "json"


class FieldView(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    key: str
    label: str
    field_type: FieldKind
    description: str = ""
    default: JsonValue = None
    placeholder: str = ""
    value: JsonValue = None


class SectionView(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    key: str
    title: str
    description: str = ""
    fields: tuple[FieldView, ...]
    revision: int
    updated_at: datetime | None = None
    on_update_action: None = None


class CategoryView(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    key: str
    title: str
    description: str = ""
    sections: tuple[SectionView, ...]


class ConfigurationView(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    categories: tuple[CategoryView, ...]
