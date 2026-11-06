"""Versioned composition configuration; identities refer to declared child aliases."""

from enum import StrEnum
from typing import Self

from mas.application.programs.ports import ChildContract
from mas.domain.programs.models import Binding, PathBinding, Projection
from pydantic import BaseModel, ConfigDict, Field, JsonValue, StrictBool, model_validator


class CompositionModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, hide_input_in_errors=True)


class BodyConfig(CompositionModel):
    body: str = Field(default="body", min_length=1, max_length=128)
    inputs: Projection | None = None


class MapScope(CompositionModel):
    item: JsonValue
    index: int = Field(ge=0)
    context: JsonValue


class MapConfig(BodyConfig):
    """All items must succeed; the first failure cancels remaining owned children."""

    concurrency: int = Field(default=4, ge=1, le=128)
    max_items: int = Field(default=1000, ge=1, le=10_000)

    def child_contracts(self) -> dict[str, ChildContract]:
        return {
            self.body: ChildContract(
                inputs=self.inputs,
                scope_schema=MapScope.model_json_schema(mode="serialization"),
            )
        }


class MapInput(CompositionModel):
    items: tuple[JsonValue, ...] = Field(max_length=10_000)
    context: JsonValue = Field(default_factory=dict)


class MapItem(CompositionModel):
    index: int = Field(ge=0)
    execution_id: str
    value: JsonValue


class MapResult(CompositionModel):
    items: tuple[MapItem, ...]


class RepeatScope(CompositionModel):
    state: JsonValue
    iteration: int = Field(ge=0)
    context: JsonValue


class RepeatProjection(CompositionModel):
    state: JsonValue
    done: StrictBool


class RepeatConfig(BodyConfig):
    max_iterations: int = Field(default=10, ge=1, le=10_000)
    state: Binding = Field(default_factory=lambda: PathBinding(path=("state",)))
    until: Binding = Field(default_factory=lambda: PathBinding(path=("done",)))

    def child_contracts(self) -> dict[str, ChildContract]:
        return {
            self.body: ChildContract(
                inputs=self.inputs,
                scope_schema=RepeatScope.model_json_schema(mode="serialization"),
                outputs={"state": self.state, "done": self.until},
                result_model=RepeatProjection,
            )
        }


class RepeatInput(CompositionModel):
    state: JsonValue
    context: JsonValue = Field(default_factory=dict)


class RepeatReason(StrEnum):
    SATISFIED = "satisfied"
    LIMIT_REACHED = "limit_reached"


class RepeatResult(CompositionModel):
    reason: RepeatReason
    iterations: int = Field(ge=1)
    state: JsonValue
    last: JsonValue
    execution_id: str


class ChooseConfig(CompositionModel):
    branches: dict[str, str] = Field(min_length=1, max_length=128)
    selector: Binding = Field(default_factory=lambda: PathBinding(path=("choice",)))
    inputs: Projection | None = None

    @model_validator(mode="after")
    def valid_branches(self) -> Self:
        if any(not label or not alias for label, alias in self.branches.items()):
            raise ValueError("Choose branches require nonempty labels and child aliases")
        return self

    def child_contracts(self) -> dict[str, ChildContract]:
        return {name: ChildContract(inputs=self.inputs) for name in self.branches.values()}


class ChooseResult(CompositionModel):
    branch: str
    execution_id: str
    value: JsonValue


class WaitConfig(CompositionModel):
    channel: str = Field(min_length=1, max_length=256)
    timeout_seconds: float = Field(default=3600, gt=0, le=2_592_000, allow_inf_nan=False)


class WaitReason(StrEnum):
    RECEIVED = "received"
    TIMED_OUT = "timed_out"


class WaitResult(CompositionModel):
    reason: WaitReason
    value: JsonValue = None
