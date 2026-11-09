"""Portable adapter payloads. These types never enter application service ports."""

from typing import Self

from pydantic import BaseModel, ConfigDict, Field, JsonValue, model_validator
from runengine.core.refs import FunctionRef

from flareward.elements.catalog.element_registry import ElementRegistry
from flareward.executions.domain.budgets import WorkLimits
from flareward.executions.domain.context import ExecutionContext
from flareward.executions.domain.placement import PreparedProgramPlacement
from flareward.programs.domain.models import Bindings, BodyPath, ProgramRef, Projection
from flareward.programs.graph.models.step_context import StepContext
from flareward.programs.registry import ApplicationRegistration
from flareward.resources.domain.bundles import ElementBundle
from flareward.resources.domain.categories import ResourceCategory


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


class ApplicationCall(BaseModel):
    """Portable installed references; the application invoker owns invocation semantics."""

    model_config = ConfigDict(extra="forbid", frozen=True)
    implementation: str = Field(min_length=1)
    version: str = Field(min_length=1)
    execute: FunctionRef
    configuration_schema: FunctionRef
    input_model: FunctionRef | None = None
    result_model: FunctionRef | None = None

    @classmethod
    def from_registration(cls, registration: ApplicationRegistration) -> Self:
        return cls(
            implementation=registration.key,
            version=registration.version,
            execute=FunctionRef.from_callable(registration.execute),
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

    def resolve(self) -> ApplicationRegistration:
        return ApplicationRegistration(
            self.implementation,
            self.version,
            self._model(self.configuration_schema),
            self.execute.resolve(),
            input_model=self._model(self.input_model) if self.input_model else None,
            result_model=self._model(self.result_model) if self.result_model else None,
        )


class WorkBudgetBinding(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    limits: WorkLimits
    admission: FunctionRef


class ProgramPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")
    program: ProgramRef
    body_path: BodyPath = ()
    content_digest: str = Field(pattern=r"^[a-f0-9]{64}$")
    input_schema: dict[str, JsonValue]
    output_schema: dict[str, JsonValue]
    context: ExecutionContext
    inputs: JsonValue = Field(default_factory=dict)
    graph_request: dict[str, JsonValue] | None = None
    graph_inputs: Bindings = Field(default_factory=dict)
    graph_outputs: Projection = Field(default_factory=dict)
    configuration: dict[str, JsonValue] = Field(default_factory=dict)
    application: ApplicationCall | None = None
    children: dict[str, dict[str, JsonValue]] = Field(default_factory=dict)
    specifications: ElementSpecifications = Field(default_factory=ElementSpecifications)
    placement: ProgramPlacement
    receiver: FunctionRef | None = None
    cancellation: FunctionRef | None = None
    work_budget: WorkBudgetBinding | None = None

    @model_validator(mode="after")
    def implementation(self) -> Self:
        if (self.graph_request is not None) == (self.application is not None):
            raise ValueError("Prepared program requires exactly one implementation")
        return self


class MappingConfiguration(BaseModel):
    bindings: Bindings


class ProjectionConfiguration(BaseModel):
    bindings: Projection
