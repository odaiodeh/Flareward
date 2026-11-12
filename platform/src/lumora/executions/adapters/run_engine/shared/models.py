"""Portable adapter payloads. These types never enter application service ports."""

from typing import Annotated, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, JsonValue, model_validator
from runengine.core.refs import FunctionRef

from lumora.elements.catalog.element_registry import ElementRegistry
from lumora.executions.domain.budgets import WorkLimits
from lumora.executions.domain.context import ExecutionContext
from lumora.executions.domain.observation import OccurrenceKind
from lumora.executions.domain.placement import PreparedProgramPlacement
from lumora.programs.domain.bindings import Bindings, Projection
from lumora.programs.domain.interfaces import CoordinatorIdentity, ProgramInterface
from lumora.programs.domain.models import BodyPath, ProgramRef
from lumora.programs.graph.models.step_context import StepContext
from lumora.programs.registry import CoordinatorRegistration, CustomCoordinatorStrategy
from lumora.resources.domain.bundles import ElementBundle
from lumora.resources.domain.categories import ResourceCategory


class ElementCall(BaseModel):
    model_config = ConfigDict(extra="forbid")
    bundle: ElementBundle
    specifications: tuple[FunctionRef, ...]
    context: ExecutionContext
    key: str = Field(min_length=1)
    step: StepContext | None = None
    receiver: FunctionRef | None = None

    @model_validator(mode="after")
    def validate_context(self) -> Self:
        if self.bundle.root.category == ResourceCategory.OPERATION:
            if self.step is not None:
                raise ValueError("Typed operation calls cannot carry graph step context")
        elif self.step is None or self.step.uid != self.key:
            raise ValueError("Graph calls require step context matching their invocation key")
        return self

    @property
    def graph_step(self) -> StepContext:
        if self.step is None:
            raise ValueError("This invocation has no graph step context")
        return self.step


class ProgramPlacement(BaseModel):
    """Frozen coordinator-only choices; concrete targets never enter application ports."""

    model_config = ConfigDict(extra="forbid", frozen=True)
    default_profile: str
    profiles: dict[str, dict[str, JsonValue]]
    environments: tuple[str, ...] = ()
    child_imports: dict[str, dict[str, str]] = Field(default_factory=dict)
    summary: PreparedProgramPlacement | None = None


class ElementSpecifications(BaseModel):
    """Installed catalog identities, selected without importing unrelated plugins."""

    model_config = ConfigDict(extra="forbid")
    catalog: dict[ResourceCategory, dict[str, FunctionRef]] = Field(default_factory=dict)

    @classmethod
    def from_registry(cls, registry: ElementRegistry) -> ElementSpecifications:
        return cls(
            catalog={
                category: {
                    key: FunctionRef.from_callable(spec) for key, spec in specifications.items()
                }
                for category, specifications in registry.get_categories_map().items()
            }
        )

    def for_bundle(self, bundle: ElementBundle) -> tuple[FunctionRef, ...]:
        identities = {
            (entry.resource.key.category, entry.resource.type_key) for entry in bundle.entries
        }
        try:
            return tuple(self.catalog[category][key] for category, key in sorted(identities))
        except KeyError:
            raise ValueError("Invocation references an unregistered element type") from None


class CoordinatorCall(BaseModel):
    """Portable installed references; the application invoker owns invocation semantics."""

    model_config = ConfigDict(extra="forbid", frozen=True)
    implementation: str = Field(min_length=1)
    version: str = Field(min_length=1)
    execute: FunctionRef
    configuration_schema: FunctionRef
    input_model: FunctionRef | None = None
    result_model: FunctionRef | None = None

    @classmethod
    def from_registration(cls, registration: CoordinatorRegistration) -> Self:
        if not isinstance(registration.strategy, CustomCoordinatorStrategy):
            raise ValueError("Custom preparation requires a custom coordinator strategy")
        return cls(
            implementation=registration.key,
            version=registration.version,
            execute=FunctionRef.from_callable(registration.strategy.entrypoint),
            configuration_schema=FunctionRef.from_callable(registration.config_schema),
            input_model=FunctionRef.from_callable(registration.input_model)
            if registration.input_model
            else None,
            result_model=FunctionRef.from_callable(registration.result_model)
            if registration.result_model
            else None,
        )

    @staticmethod
    def _model(reference: FunctionRef) -> type[BaseModel]:
        schema = reference.resolve()
        if not isinstance(schema, type) or not issubclass(schema, BaseModel):
            raise ValueError("Installed Program schema is not a Pydantic model")
        return schema

    def resolve(self) -> CoordinatorRegistration:
        return CoordinatorRegistration(
            self.implementation,
            self.version,
            self._model(self.configuration_schema),
            CustomCoordinatorStrategy(self.execute.resolve()),
            input_model=self._model(self.input_model) if self.input_model else None,
            result_model=self._model(self.result_model) if self.result_model else None,
        )


class WorkBudgetBinding(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    limits: WorkLimits
    admission: FunctionRef


class PreparedGraph(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    kind: Literal["graph"] = "graph"
    sites: dict[str, OccurrenceKind] = Field(default_factory=dict)
    request: dict[str, JsonValue]
    inputs: Bindings = Field(default_factory=dict)
    outputs: Projection = Field(default_factory=dict)


class PreparedCoordinator(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    kind: Literal["coordinator"] = "coordinator"
    call: CoordinatorCall
    configuration: dict[str, JsonValue] = Field(default_factory=dict)
    children: dict[str, dict[str, JsonValue]] = Field(default_factory=dict)


type PreparedImplementation = Annotated[
    PreparedGraph | PreparedCoordinator, Field(discriminator="kind")
]


class ProgramPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")
    program: ProgramRef
    body_path: BodyPath = ()
    call_site: str | None = Field(default=None, min_length=1)
    content_digest: str = Field(pattern=r"^[a-f0-9]{64}$")
    interface: ProgramInterface
    context: ExecutionContext
    inputs: JsonValue = Field(default_factory=dict)
    implementation: PreparedImplementation
    specifications: ElementSpecifications = Field(default_factory=ElementSpecifications)
    placement: ProgramPlacement
    receiver: FunctionRef | None = None
    cancellation: FunctionRef | None = None
    work_budget: WorkBudgetBinding | None = None

    @model_validator(mode="after")
    def validate_interface(self) -> Self:
        if self.interface.children:
            raise ValueError("Prepared interfaces must be local to one Program body")
        if isinstance(self.implementation, PreparedGraph) and (
            self.interface.coordinator != CoordinatorIdentity(key="graph", version="1")
            or self.interface.configured is not None
            or self.interface.dependencies
            or self.interface.input_model_schema is not None
            or self.interface.output_model_schema is not None
            or self.interface.normalized_input_schema is not None
            or self.interface.normalized_output_schema is not None
        ):
            raise ValueError("Native graph interface does not match its coordinator")
        return self


class MappingConfiguration(BaseModel):
    bindings: Bindings


class ProjectionConfiguration(BaseModel):
    bindings: Projection
