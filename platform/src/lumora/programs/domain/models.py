"""Portable Program definitions, bindings and publication invariants."""

import hashlib
import json
from enum import StrEnum
from typing import Annotated, ClassVar, Literal, Self

from pydantic import BeforeValidator, Field, JsonValue, model_validator

from lumora.executions.domain.preferences import ExecutionSelection
from lumora.models import Model
from lumora.programs.domain.bindings import Binding, Bindings, Projection
from lumora.programs.domain.interfaces import ProgramInterface
from lumora.programs.domain.metadata import StepMeta
from lumora.resources.domain.bundles import ResourceDefinition, ResourceKey
from lumora.resources.domain.categories import ResourceCategory
from lumora.services.identity.domain import Identity


def _object_schema() -> dict[str, JsonValue]:
    return {"type": "object"}


class ProgramKind(StrEnum):
    GRAPH = "graph"
    APPLICATION = "application"


class StepKind(StrEnum):
    ELEMENT = "element"
    OPERATION = "operation"
    PROGRAM = "program"


class JoinPolicy(StrEnum):
    ACTIVE = "active"
    ALL = "all"


class GraphWritePolicy(StrEnum):
    ORDERED = "ordered"
    REDUCE = "reduce"


class ProgramRef(Model):
    program_id: str = Field(min_length=1)
    revision: int = Field(ge=1)


type BodyPath = tuple[Annotated[str, Field(min_length=1)], ...]


def _owned_target(value: object) -> object:
    if isinstance(value, ProgramDefinition):
        raise ValueError("Use a published reference or an explicitly owned program body")
    return value


type ProgramTarget = Annotated[ProgramRef | ProgramBody, BeforeValidator(_owned_target)]


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


class OperationStep(Model):
    kind: Literal[StepKind.OPERATION] = StepKind.OPERATION
    uid: str = Field(min_length=1)
    element: ResourceKey
    inputs: Projection = Field(default_factory=dict)
    outputs: Bindings = Field(default_factory=dict)
    execution: ExecutionSelection = Field(default_factory=ExecutionSelection)
    max_attempts: int = Field(default=1, ge=1)
    metadata: StepMeta = Field(default_factory=StepMeta)

    @model_validator(mode="after")
    def operation_resource(self) -> Self:
        if self.element.category != ResourceCategory.OPERATION:
            raise ValueError("An operation graph step must reference an operation resource")
        return self


class ProgramCallStep(Model):
    kind: Literal[StepKind.PROGRAM] = StepKind.PROGRAM
    uid: str = Field(min_length=1)
    program: ProgramTarget
    inputs: Projection = Field(default_factory=dict)
    outputs: Bindings = Field(default_factory=dict)
    environment_imports: dict[str, str] = Field(default_factory=dict)
    max_attempts: int = Field(default=1, ge=1)
    metadata: StepMeta = Field(default_factory=StepMeta)


type GraphStep = Annotated[
    ElementStep | OperationStep | ProgramCallStep, Field(discriminator="kind")
]


class RouteKind(StrEnum):
    CONDITION = "condition"
    RESULT = "result"


class ConditionalRoute(Model):
    kind: Literal[RouteKind.CONDITION] = RouteKind.CONDITION
    source: str
    condition: ResourceKey
    branches: dict[str, str]
    execution: ExecutionSelection = Field(default_factory=ExecutionSelection)

    @model_validator(mode="after")
    def condition_resource(self) -> Self:
        if self.condition.category != ResourceCategory.CONDITION:
            raise ValueError("A route must reference a condition resource")
        return self


class ResultRoute(Model):
    """Select declared labels from data available after the source step completes."""

    kind: Literal[RouteKind.RESULT] = RouteKind.RESULT
    source: str
    selection: Binding
    branches: dict[str, str]
    execution: ExecutionSelection = Field(default_factory=ExecutionSelection)


type GraphRoute = Annotated[ConditionalRoute | ResultRoute, Field(discriminator="kind")]


class GraphDefinition(Model):
    INPUT_CHANNEL: ClassVar[str] = "input"
    RESULTS_CHANNEL: ClassVar[str] = "results"
    READ_ONLY_CHANNELS: ClassVar[frozenset[str]] = frozenset({INPUT_CHANNEL, RESULTS_CHANNEL})
    kind: Literal[ProgramKind.GRAPH] = ProgramKind.GRAPH
    steps: tuple[GraphStep, ...]
    resources: tuple[ResourceDefinition, ...] = ()
    edges: dict[str, tuple[str, ...]] = Field(default_factory=dict)
    conditions: tuple[GraphRoute, ...] = ()
    entry: str = ""
    exit: str = ""
    inputs: Bindings = Field(default_factory=dict)
    outputs: Projection = Field(default_factory=dict)
    environments: dict[str, str] = Field(default_factory=dict)
    recursion_limit: int = Field(default=100, ge=1)
    join_policy: JoinPolicy = JoinPolicy.ACTIVE
    write_policy: GraphWritePolicy = GraphWritePolicy.ORDERED

    @model_validator(mode="after")
    def unique_identities(self) -> Self:
        self._validate_identities()
        return self

    def _validate_identities(self) -> None:
        uids = {step.uid for step in self.steps}
        if len(uids) != len(self.steps):
            raise ValueError("Graph step identifiers must be unique")
        sources = {condition.source for condition in self.conditions}
        if len(sources) != len(self.conditions):
            raise ValueError("Only one condition is allowed per source step")

    def validate_executable(self) -> None:
        """Draft topology can be unfinished; a published graph must be complete."""
        self._validate_identities()
        uids = {step.uid for step in self.steps}
        if self.entry not in uids or self.exit not in uids:
            raise ValueError("Graph entry and exit must identify existing steps")
        for source, targets in self.edges.items():
            if source not in uids or not set(targets) <= uids:
                raise ValueError("Graph edge references an unknown step")
        for condition in self.conditions:
            if condition.source not in uids or not set(condition.branches.values()) <= uids:
                raise ValueError("Conditional route references an unknown step")
            if not condition.branches:
                raise ValueError("Conditional route must declare a destination")
            if self.edges.get(condition.source):
                raise ValueError("A conditional source cannot also declare ordinary successors")


class CustomCoordinatorDefinition(Model):
    kind: Literal[ProgramKind.APPLICATION] = ProgramKind.APPLICATION
    implementation: str = Field(min_length=1)
    version: str = Field(min_length=1)
    config: dict[str, JsonValue] = Field(default_factory=dict)
    children: dict[Annotated[str, Field(min_length=1)], ProgramTarget] = Field(default_factory=dict)
    environments: dict[str, str] = Field(default_factory=dict)
    child_environment_imports: dict[str, dict[str, str]] = Field(default_factory=dict)

    def validate_executable(self) -> None:
        if not self.child_environment_imports.keys() <= self.children.keys():
            raise ValueError("Environment imports must identify a declared child program")


type ProgramImplementation = Annotated[
    GraphDefinition | CustomCoordinatorDefinition, Field(discriminator="kind")
]


class ProgramDependency(Model):
    """One declared Program target and its explicit environment access."""

    program: ProgramTarget
    environment_imports: dict[str, str] = Field(default_factory=dict)
    source: tuple[str | int, ...]


class ProgramBody(Model):
    """Owned coordination with no independent library identity or authority."""

    implementation: ProgramImplementation
    input_schema: dict[str, JsonValue] = Field(default_factory=_object_schema)
    output_schema: dict[str, JsonValue] = Field(default_factory=_object_schema)
    execution_profile: str | None = None

    @property
    def dependencies(self) -> dict[str, ProgramDependency]:
        implementation = self.implementation
        if isinstance(implementation, GraphDefinition):
            return {
                step.uid: ProgramDependency(
                    program=step.program,
                    environment_imports=step.environment_imports,
                    source=("implementation", "steps", index, "program"),
                )
                for index, step in enumerate(implementation.steps)
                if isinstance(step, ProgramCallStep)
            }
        return {
            name: ProgramDependency(
                program=target,
                environment_imports=implementation.child_environment_imports.get(name, {}),
                source=("implementation", "children", name),
            )
            for name, target in implementation.children.items()
        }

    @property
    def program_calls(self) -> dict[str, ProgramTarget]:
        return {name: dependency.program for name, dependency in self.dependencies.items()}

    def body_at(self, path: BodyPath) -> ProgramBody:
        body: ProgramBody = self
        for name in path:
            target = body.program_calls.get(name)
            if not isinstance(target, ProgramBody):
                raise ValueError("Owned body path does not identify an inline program")
            body = target
        return body

    def with_program_calls(self, calls: dict[str, ProgramTarget]) -> Self:
        if calls.keys() != self.program_calls.keys():
            raise ValueError("Program call replacement must preserve authored identities")
        implementation = self.implementation
        if isinstance(implementation, GraphDefinition):
            implementation = implementation.model_copy(
                update={
                    "steps": tuple(
                        step.model_copy(update={"program": calls[step.uid]})
                        if isinstance(step, ProgramCallStep)
                        else step
                        for step in implementation.steps
                    )
                }
            )
        else:
            implementation = implementation.model_copy(update={"children": dict(calls)})
        return self.model_copy(update={"implementation": implementation}, deep=True)

    def validate_executable(self) -> None:
        self.implementation.validate_executable()
        for target in self.program_calls.values():
            if isinstance(target, ProgramBody):
                target.validate_executable()


class ProgramDefinition(ProgramBody):
    program_id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    owner: Identity


class ProgramRevision(Model):
    definition: ProgramDefinition
    interface: ProgramInterface
    revision: int = Field(ge=1)
    content_digest: str = ""

    @property
    def reference(self) -> ProgramRef:
        return ProgramRef(program_id=self.definition.program_id, revision=self.revision)

    @model_validator(mode="after")
    def check_digest(self) -> Self:
        self.definition.validate_executable()
        pending = [(self.definition, self.interface)]
        while pending:
            body, interface = pending.pop()
            implementation = body.implementation
            identity = (
                ("graph", "1")
                if isinstance(implementation, GraphDefinition)
                else (implementation.implementation, implementation.version)
            )
            owned = {
                name: target
                for name, target in body.program_calls.items()
                if isinstance(target, ProgramBody)
            }
            if (
                (interface.coordinator.key, interface.coordinator.version) != identity
                or interface.input_schema != body.input_schema
                or interface.output_schema != body.output_schema
                or interface.children.keys() != owned.keys()
                or not interface.dependencies.keys() <= body.program_calls.keys()
            ):
                raise ValueError("Published interface does not match its Program body")
            pending.extend((target, interface.children[name]) for name, target in owned.items())
        data = self.model_dump(mode="json", exclude={"content_digest"})
        encoded = json.dumps(data, sort_keys=True, separators=(",", ":"), allow_nan=False)
        digest = hashlib.sha256(encoded.encode()).hexdigest()
        if self.content_digest and self.content_digest != digest:
            raise ValueError("Program revision content digest mismatch")
        object.__setattr__(self, "content_digest", digest)
        return self


ProgramDependency.model_rebuild()
ProgramBody.model_rebuild()
ProgramCallStep.model_rebuild()
GraphDefinition.model_rebuild()
CustomCoordinatorDefinition.model_rebuild()
