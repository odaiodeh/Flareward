from datetime import UTC, datetime
from typing import Annotated, Self
from uuid import uuid4

from pydantic import BaseModel, Field, JsonValue, field_validator, model_validator

from flareward.executions.domain.preferences import ResourceExecutionDefaults
from flareward.resources.domain.categories import ResourceCategory
from flareward.services.identity.domain import Identity


class Resource(BaseModel):
    """
    One persisted element in the user's Library.

    cfg_dict is plain JSON; we do NOT store the Pydantic instance.

    Built-in-specific metadata (ownership, visibility, parent_builtin_id)
    does NOT live here — it lives in the separate
    ``builtin_resource_descriptors`` collection, joined by ``rid``. See
    ``BuiltinResourceDescriptor`` (``flareward.resources.domain.builtins``) and
    ``BuiltinAdministration``, which owns that descriptor's full
    lifecycle. A resource with no matching descriptor is a plain custom
    resource — existence of a descriptor *is* the "this resource is a
    built-in" signal, so ``Resource`` carries zero built-in-related
    fields or knowledge.
    """

    rid: str = Field(default_factory=lambda: uuid4().hex)
    identity: Identity
    category: ResourceCategory
    type: str
    name: str
    execution: ResourceExecutionDefaults = Field(default_factory=ResourceExecutionDefaults)
    version: int = Field(default=1, ge=1)
    cfg_dict: dict[str, JsonValue]
    nested_refs: list[str] = Field(default_factory=list)
    contributed_by: str | None = None
    created: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @model_validator(mode="after")
    def validate_execution(self) -> Self:
        self.execution.validate_category(self.category)
        return self


class ResourceQuery(BaseModel):
    """Query object for finding resources with pagination and filtering.

    Purely identity/category/type/pagination/sort — no ownership/is_admin
    concept. Listing that needs to reason about built-in visibility (the
    ``ownership`` query filter on ``/resources.list``) is handled by
    ``BuiltinAdministration`` via the joined
    ``BuiltinResourceDescriptorRepository`` reads, not by this query object
    or the base ``ResourceRepository``.
    """

    identity: Identity = Field(..., description="Owner identity to filter resources")
    category: ResourceCategory | None = Field(None, description="Resource category filter")
    type: str | None = Field(None, description="Resource type filter")

    limit: Annotated[int, Field(50, ge=1, le=1000, description="Number of results to return")]
    offset: Annotated[int, Field(0, ge=0, description="Number of results to skip")]

    sort_by: str = Field("created", description="Field to sort by")
    sort_order: Annotated[str, Field("desc", pattern="^(asc|desc)$", description="Sort direction")]

    @field_validator("sort_by")
    @classmethod
    def validate_sort_by(cls, v: str) -> str:
        allowed_fields = {"created", "updated", "name", "type", "category"}
        if v not in allowed_fields:
            raise ValueError(f"sort_by must be one of: {allowed_fields}")
        return v
