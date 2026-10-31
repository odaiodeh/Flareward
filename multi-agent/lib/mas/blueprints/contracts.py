"""Resolved blueprint metadata consumed without loading vendor-specific schemas."""

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Annotated, Protocol

from pydantic import BaseModel, ConfigDict, Field, JsonValue, field_validator

from mas.application.elements.construction.collections import ResourceCollections
from mas.core.identity import Identity
from mas.core.resource_models import BlueprintResource, StepDef


class ResolvedBlueprint(ResourceCollections, Protocol):
    plan: Iterable[StepDef]
    name: str
    description: str
    execution_profile: str | None
    environments: dict[str, str]


class BlueprintTemplate(Protocol):
    providers: Iterable[BlueprintResource]
    llms: Iterable[BlueprintResource]
    retrievers: Iterable[BlueprintResource]
    tools: Iterable[BlueprintResource]
    sandboxes: Iterable[BlueprintResource]
    nodes: Iterable[BlueprintResource]
    conditions: Iterable[BlueprintResource]
    plan: Iterable[StepDef]
    name: str
    description: str
    execution_profile: str | None
    environments: dict[str, str]


class BlueprintExecutionSettings(BaseModel):
    """Workflow placement authoring; concrete runners remain deployment-owned."""

    execution_profile: str | None = Field(default=None, min_length=1)
    environments: dict[Annotated[str, Field(min_length=1)], Annotated[str, Field(min_length=1)]] = (
        Field(default_factory=dict)
    )


type BlueprintData = dict[str, JsonValue]


@dataclass(frozen=True)
class BlueprintResolution:
    blueprint: ResolvedBlueprint
    missing: dict[str, str]


class BlueprintResolutionSource(Protocol):
    async def resolve(
        self, spec: BlueprintData, caller: Identity, *, stored: bool
    ) -> BlueprintResolution: ...


class BlueprintDocument(BaseModel):
    """Stored authoring data, independent of installed element configuration schemas."""

    model_config = ConfigDict(extra="ignore")
    blueprint_id: str
    identity: Identity
    created_at: datetime | None = None
    updated_at: datetime | None = None
    spec_dict: BlueprintData
    rid_refs: list[str] = Field(default_factory=list)
    metadata: BlueprintData = Field(default_factory=dict)
    version: int = Field(default=0, ge=0)

    @field_validator("created_at", "updated_at")
    @classmethod
    def normalize_timestamp(cls, value: datetime | None) -> datetime | None:
        if value is None or value.tzinfo is not None:
            return value
        return value.replace(tzinfo=UTC)


class BlueprintSummary(BaseModel):
    blueprint_id: str
    identity: Identity
    name: str = "Untitled blueprint"
    description: str = ""
    created_at: datetime | None = None
    updated_at: datetime | None = None
    metadata: BlueprintData = Field(default_factory=dict)


class BlueprintPage(BaseModel):
    items: list[BlueprintDocument]
    total: int = Field(ge=0)
    skip: int = Field(ge=0)
    limit: int = Field(ge=1, le=1000)


class BlueprintView(BlueprintDocument):
    """A resolved display snapshot, never an editable or executable configuration."""

    missing_resources: dict[str, str] = Field(default_factory=dict)


class BlueprintViews(BaseModel):
    items: list[BlueprintView]
    total: int = Field(ge=0)
    skip: int = Field(ge=0)
    limit: int = Field(ge=1, le=1000)


class BlueprintAuthoringRepository(Protocol):
    async def create(self, document: BlueprintDocument) -> None: ...
    async def get(self, blueprint_id: str) -> BlueprintDocument: ...
    async def replace(self, previous: BlueprintDocument, updated: BlueprintDocument) -> bool: ...
    async def delete(self, previous: BlueprintDocument) -> bool: ...
    async def list(
        self, identity: Identity, *, skip: int, limit: int, sort_desc: bool
    ) -> BlueprintPage: ...
