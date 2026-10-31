"""Portable adapter payloads. These types never enter application service ports."""

from mas.core.execution_context import ExecutionContext
from mas.domain.element_bundles import ElementBundle
from mas.graph.models.step_context import StepContext
from mas.programs.models import Bindings, ProgramRevision
from pydantic import BaseModel, ConfigDict, Field, JsonValue
from runengine.core.refs import FunctionRef


class ElementCall(BaseModel):
    model_config = ConfigDict(extra="forbid")
    bundle: ElementBundle
    specifications: tuple[FunctionRef, ...]
    context: ExecutionContext
    step: StepContext
    receiver: FunctionRef | None = None


class ProgramPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")
    revision: ProgramRevision
    context: ExecutionContext
    inputs: JsonValue = Field(default_factory=dict)
    graph_request: dict[str, JsonValue] | None = None
    application_function: FunctionRef | None = None
    configuration_schema: FunctionRef | None = None
    children: dict[str, dict[str, JsonValue]] = Field(default_factory=dict)
    specifications: tuple[FunctionRef, ...] = ()
    element_target: dict[str, JsonValue] | None = None
    receiver: FunctionRef | None = None
    cancellation: FunctionRef | None = None


class MappingConfiguration(BaseModel):
    bindings: Bindings
