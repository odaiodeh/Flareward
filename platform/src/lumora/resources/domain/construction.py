"""Shared configuration and graph metadata, independent of concrete SDK schemas."""

from datetime import datetime
from typing import Self
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, SerializeAsAny, model_validator

from lumora.executions.domain.preferences import ExecutionSelection, ResourceExecutionDefaults
from lumora.programs.domain.metadata import StepMeta
from lumora.resources.domain.references import ConditionRef, NodeRef, Ref


class BlueprintExecutionStats(BaseModel):
    """Pre-aggregated execution statistics returned by blueprint repositories."""

    blueprint_id: str
    total_runs: int = 0
    completed_runs: int = 0
    failed_runs: int = 0
    active_runs: int = 0
    last_run: datetime | None = None
    avg_duration_ms: float | None = None
    users: list[str] = Field(default_factory=list)


class BlueprintResource[T: BaseModel](BaseModel):
    """Authoring resource: inline configuration or a catalog reference."""

    model_config = ConfigDict(extra="forbid")
    rid: Ref
    name: str | None = None
    type: str | None = None
    config: SerializeAsAny[T] | None = None
    execution: ResourceExecutionDefaults | None = None


class ResourceSpec[T: BaseModel](BaseModel):
    """Resolved resource configuration, retaining concrete configuration fields."""

    model_config = ConfigDict(extra="forbid")
    rid: Ref
    name: str
    type: str
    config: SerializeAsAny[T]
    execution: ResourceExecutionDefaults = Field(default_factory=ResourceExecutionDefaults)


class StepDef(BaseModel):
    """Blueprint step authoring data, independent of concrete integration schemas."""

    model_config = ConfigDict(extra="forbid")
    uid: str = Field(default_factory=lambda: f"s_{uuid4().hex[:8]}")
    after: str | list[str] | None = None
    node: NodeRef
    exit_condition: ConditionRef | None = None
    branches: dict | None = None
    meta: StepMeta = Field(default_factory=StepMeta)
    execution: ExecutionSelection | None = None
    condition_execution: ExecutionSelection | None = None

    @model_validator(mode="after")
    def require_condition_for_placement(self) -> Self:
        if self.condition_execution is not None and self.exit_condition is None:
            raise ValueError("Condition placement requires an exit condition")
        return self
