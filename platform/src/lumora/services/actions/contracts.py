"""Typed action metadata and invocation boundaries, independent of HTTP and providers."""

from abc import ABC, abstractmethod
from enum import StrEnum
from typing import Any, Protocol

from pydantic import BaseModel, ConfigDict, Field, JsonValue

from lumora.resources.domain.categories import ResourceCategory
from lumora.services.identity.domain import Identity


class ActionType(StrEnum):
    VALIDATION = "validation"
    DISCOVERY = "discovery"
    UTILITY = "utility"


class BaseActionInput(BaseModel):
    # Existing form actions send a subset of shared configuration fields.
    model_config = ConfigDict(extra="ignore")


class BaseActionOutput(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    success: bool
    message: str


class ActionSettings(Protocol):
    async def get_section(self, key: str) -> dict[str, JsonValue] | None: ...


class ActionContext(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    owner: Identity
    credential_user_id: str = Field(min_length=1)
    data: dict[str, JsonValue] = Field(default_factory=dict)


class ActionElement(BaseModel):
    category: ResourceCategory
    type: str


class ActionMetadata(BaseModel):
    uid: str = Field(min_length=1)
    name: str = Field(min_length=1)
    description: str
    action_type: ActionType
    version: str
    tags: tuple[str, ...]
    elements: tuple[ActionElement, ...]
    input_schema: dict[str, Any]
    output_schema: dict[str, Any]


class BaseAction[Input: BaseModel, Output: BaseModel](ABC):
    uid: str
    name: str
    description: str
    action_type: ActionType
    input_schema: type[Input]
    output_schema: type[Output]
    version: str = "1.0.0"
    tags: frozenset[str] = frozenset()
    elements: frozenset[tuple[str, str]] = frozenset()

    @abstractmethod
    async def execute(self, input_data: Input, context: ActionContext) -> Output: ...

    @classmethod
    def get_metadata(cls) -> ActionMetadata:
        return ActionMetadata(
            uid=cls.uid,
            name=cls.name,
            description=cls.description,
            action_type=cls.action_type,
            version=cls.version,
            tags=tuple(sorted(cls.tags)),
            elements=tuple(
                ActionElement(category=ResourceCategory(c), type=t) for c, t in sorted(cls.elements)
            ),
            input_schema=cls.input_schema.model_json_schema(),
            output_schema=cls.output_schema.model_json_schema(),
        )
