"""Coordinator specifications for native graph and plugin behavior."""

from dataclasses import dataclass
from inspect import iscoroutinefunction

from pydantic import BaseModel, ConfigDict, JsonValue

from lumora.programs.domain.models import (
    CustomCoordinatorDefinition,
    GraphDefinition,
    ProgramBody,
    ProgramKind,
)
from lumora.programs.ports import ChildContract, ChildContracts, CoordinatorEntrypoint


class CoordinatorDescriptor(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    key: str
    version: str
    name: str
    description: str
    configuration_schema: dict[str, JsonValue]
    kind: ProgramKind
    input_schema: dict[str, JsonValue] | None = None
    output_schema: dict[str, JsonValue] | None = None


@dataclass(frozen=True)
class NativeGraphStrategy:
    """Graph coordination is prepared and delegated by the execution adapter."""


@dataclass(frozen=True)
class CustomCoordinatorStrategy:
    """Installed async coordination using the application-owned runtime port."""

    entrypoint: CoordinatorEntrypoint

    def __post_init__(self) -> None:
        if not iscoroutinefunction(self.entrypoint):
            raise ValueError("Coordinator entrypoints must be async functions")


type CoordinatorStrategy = NativeGraphStrategy | CustomCoordinatorStrategy


@dataclass(frozen=True)
class CoordinatorRegistration:
    key: str
    version: str
    config_schema: type[BaseModel]
    strategy: CoordinatorStrategy
    name: str = ""
    description: str = ""
    input_model: type[BaseModel] | None = None
    result_model: type[BaseModel] | None = None

    def __post_init__(self) -> None:
        if any(
            not isinstance(value, str) or not value.strip() for value in (self.key, self.version)
        ):
            raise ValueError("Program implementations require a key and version")
        for schema in (self.config_schema, self.input_model, self.result_model):
            if schema is not None and (
                not isinstance(schema, type) or not issubclass(schema, BaseModel)
            ):
                raise ValueError("Program schemas must be Pydantic model classes")
        if self.config_schema is None:
            raise ValueError("Program implementations require a configuration schema")
        if isinstance(self.strategy, NativeGraphStrategy):
            if self.key != "graph" or self.config_schema is not GraphDefinition:
                raise ValueError("Graph coordination requires the native graph specification")
        elif not isinstance(self.strategy, CustomCoordinatorStrategy):
            raise ValueError("Coordinator registration requires an explicit execution strategy")
        elif self.key == "graph" or self.config_schema is GraphDefinition:
            raise ValueError("Graph coordination requires the native graph strategy")

    @property
    def kind(self) -> ProgramKind:
        return (
            ProgramKind.GRAPH
            if isinstance(self.strategy, NativeGraphStrategy)
            else ProgramKind.APPLICATION
        )

    def configuration(self, definition: CustomCoordinatorDefinition | GraphDefinition) -> BaseModel:
        if self.kind != definition.kind:
            raise ValueError("Program definition does not match its coordinator specification")
        if isinstance(definition, GraphDefinition):
            return self.config_schema.model_validate(definition.model_dump(mode="json"))
        return self.config_schema.model_validate(definition.config, by_name=True)

    @staticmethod
    def dependency_contracts(configuration: BaseModel | None) -> dict[str, ChildContract]:
        declarations = (
            configuration.child_contracts() if isinstance(configuration, ChildContracts) else {}
        )
        if not isinstance(declarations, dict) or any(
            not isinstance(name, str) or not name or not isinstance(contract, ChildContract)
            for name, contract in declarations.items()
        ):
            raise ValueError("Program dependencies require named ChildContract declarations")
        return declarations

    def descriptor(self) -> CoordinatorDescriptor:
        return CoordinatorDescriptor(
            key=self.key,
            version=self.version,
            name=self.name or self.key,
            description=self.description,
            configuration_schema=self.config_schema.model_json_schema(),
            kind=self.kind,
            input_schema=self.input_model.model_json_schema() if self.input_model else None,
            output_schema=self.result_model.model_json_schema(mode="serialization", by_alias=False)
            if self.result_model
            else None,
        )


class CoordinatorRegistry:
    def __init__(self) -> None:
        self._implementations: dict[tuple[str, str], CoordinatorRegistration] = {}
        self.register(
            CoordinatorRegistration(
                key="graph",
                version="1",
                config_schema=GraphDefinition,
                strategy=NativeGraphStrategy(),
                name="Compose on canvas",
                description="Coordinate Operations and Programs with a graph.",
            )
        )

    def register(self, registration: CoordinatorRegistration) -> None:
        identity = registration.key, registration.version
        if identity in self._implementations:
            raise ValueError(f"Coordinator already registered: {identity}")
        self._implementations[identity] = registration

    def get(self, key: str, version: str) -> CoordinatorRegistration:
        try:
            return self._implementations[key, version]
        except KeyError as error:
            raise ValueError(f"Coordinator is not installed: {key}@{version}") from error

    def for_body(self, body: ProgramBody) -> CoordinatorRegistration:
        implementation = body.implementation
        if isinstance(implementation, GraphDefinition):
            return self.get("graph", "1")
        registration = self.get(implementation.implementation, implementation.version)
        if registration.kind != implementation.kind:
            raise ValueError("Program definition does not match its coordinator specification")
        return registration

    def describe(self) -> list[CoordinatorDescriptor]:
        return [self._implementations[key].descriptor() for key in sorted(self._implementations)]
