"""Authoring contracts. No engine, HTTP, or persistence types belong here."""

import hashlib
import json
from enum import StrEnum
from typing import Annotated, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, JsonValue, model_validator

from mas.core.enums import ResourceCategory
from mas.core.execution_preferences import ExecutionSelection as ExecutionSelection
from mas.core.identity import Identity
from mas.core.resource_models import StepMeta
from mas.domain.element_bundles import ResourceDefinition, ResourceKey


class Model(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class ProgramKind(StrEnum):
    GRAPH = "graph"
    APPLICATION = "application"


class StepKind(StrEnum):
    ELEMENT = "element"
    PROGRAM = "program"


class BindingKind(StrEnum):
    PATH = "path"
    LITERAL = "literal"


class ProgramRef(Model):
    program_id: str = Field(min_length=1)
    revision: int = Field(ge=1)


class PathBinding(Model):
    kind: Literal[BindingKind.PATH] = BindingKind.PATH
    path: tuple[str | int, ...]


class LiteralBinding(Model):
    kind: Literal[BindingKind.LITERAL] = BindingKind.LITERAL
    value: JsonValue


type Binding = Annotated[PathBinding | LiteralBinding, Field(discriminator="kind")]
type Bindings = dict[str, Binding]


class ElementStep(Model):
    kind: Literal[StepKind.ELEMENT] = StepKind.ELEMENT
    uid: str = Field(min_length=1)
    element: ResourceKey
    execution: ExecutionSelection = Field(default_factory=ExecutionSelection)
    max_attempts: int = Field(default=1, ge=1)
    description: str = ""
    metadata: StepMeta = Field(default_factory=StepMeta)

    @model_validator(mode="after")
    def node_resource(self) -> Self:
        if self.element.category != ResourceCategory.NODE:
            raise ValueError("An element graph step must reference a node resource")
        return self


class ProgramCallStep(Model):
    kind: Literal[StepKind.PROGRAM] = StepKind.PROGRAM
    uid: str = Field(min_length=1)
    program: ProgramRef
    inputs: Bindings = Field(default_factory=dict)
    outputs: Bindings = Field(default_factory=dict)
    environment_imports: dict[str, str] = Field(default_factory=dict)
    max_attempts: int = Field(default=1, ge=1)
    metadata: StepMeta = Field(default_factory=StepMeta)


type GraphStep = Annotated[ElementStep | ProgramCallStep, Field(discriminator="kind")]


class ConditionalRoute(Model):
    source: str
    condition: ResourceKey
    branches: dict[str, str]
    execution: ExecutionSelection = Field(default_factory=ExecutionSelection)

    @model_validator(mode="after")
    def condition_resource(self) -> Self:
        if self.condition.category != ResourceCategory.CONDITION:
            raise ValueError("A route must reference a condition resource")
        return self


class GraphDefinition(Model):
    kind: Literal[ProgramKind.GRAPH] = ProgramKind.GRAPH
    steps: tuple[GraphStep, ...]
    resources: tuple[ResourceDefinition, ...] = ()
    edges: dict[str, tuple[str, ...]] = Field(default_factory=dict)
    conditions: tuple[ConditionalRoute, ...] = ()
    entry: str
    exit: str
    inputs: Bindings = Field(default_factory=dict)
    outputs: Bindings = Field(default_factory=dict)
    environments: dict[str, str] = Field(default_factory=dict)
    recursion_limit: int = Field(default=100, ge=1)

    @model_validator(mode="after")
    def validate_topology(self) -> Self:
        uids = {step.uid for step in self.steps}
        if len(uids) != len(self.steps):
            raise ValueError("Graph step identifiers must be unique")
        if self.entry not in uids or self.exit not in uids:
            raise ValueError("Graph entry and exit must identify existing steps")
        for source, targets in self.edges.items():
            if source not in uids or not set(targets) <= uids:
                raise ValueError("Graph edge references an unknown step")
        sources: set[str] = set()
        for condition in self.conditions:
            if condition.source in sources:
                raise ValueError("Only one condition is allowed per source step")
            if condition.source not in uids or not set(condition.branches.values()) <= uids:
                raise ValueError("Conditional route references an unknown step")
            sources.add(condition.source)
        return self


class ApplicationDefinition(Model):
    kind: Literal[ProgramKind.APPLICATION] = ProgramKind.APPLICATION
    implementation: str = Field(min_length=1)
    version: str = Field(min_length=1)
    config: dict[str, JsonValue] = Field(default_factory=dict)
    children: dict[str, ProgramRef] = Field(default_factory=dict)


type ProgramImplementation = Annotated[
    GraphDefinition | ApplicationDefinition, Field(discriminator="kind")
]


class ProgramDefinition(Model):
    program_id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    owner: Identity
    implementation: ProgramImplementation
    input_schema: dict[str, JsonValue] = Field(default_factory=lambda: {"type": "object"})
    output_schema: dict[str, JsonValue] = Field(default_factory=lambda: {"type": "object"})
    execution_profile: str | None = None


class ProgramRevision(Model):
    definition: ProgramDefinition
    revision: int = Field(ge=1)
    content_digest: str = ""

    @property
    def reference(self) -> ProgramRef:
        return ProgramRef(program_id=self.definition.program_id, revision=self.revision)

    @model_validator(mode="after")
    def check_digest(self) -> Self:
        data = self.model_dump(mode="json", exclude={"content_digest"})
        encoded = json.dumps(data, sort_keys=True, separators=(",", ":"), allow_nan=False)
        digest = hashlib.sha256(encoded.encode()).hexdigest()
        if self.content_digest and self.content_digest != digest:
            raise ValueError("Program revision content digest mismatch")
        object.__setattr__(self, "content_digest", digest)
        return self
