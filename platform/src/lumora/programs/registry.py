"""Explicit application-program registration, owned by the composition root."""

from dataclasses import dataclass
from inspect import iscoroutinefunction

from pydantic import BaseModel, ConfigDict, JsonValue

from lumora.programs.domain.models import ApplicationDefinition
from lumora.programs.ports import ApplicationProgram, ChildContracts


class ApplicationDescriptor(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    key: str
    version: str
    name: str
    description: str
    configuration_schema: dict[str, JsonValue]
    input_schema: dict[str, JsonValue] | None = None
    output_schema: dict[str, JsonValue] | None = None


@dataclass(frozen=True)
class ApplicationRegistration:
    key: str
    version: str
    config_schema: type[BaseModel]
    execute: ApplicationProgram
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
        if not iscoroutinefunction(self.execute):
            raise ValueError("Program entrypoints must be async functions")

    def configuration(self, definition: ApplicationDefinition) -> BaseModel:
        config = self.config_schema.model_validate(definition.config, by_name=True)
        if (
            isinstance(config, ChildContracts)
            and not config.child_contracts().keys() <= definition.children.keys()
        ):
            raise ValueError("Application configuration refers to undeclared child programs")
        return config

    def descriptor(self) -> ApplicationDescriptor:
        return ApplicationDescriptor(
            key=self.key,
            version=self.version,
            name=self.name or self.key,
            description=self.description,
            configuration_schema=self.config_schema.model_json_schema(),
            input_schema=self.input_model.model_json_schema() if self.input_model else None,
            output_schema=self.result_model.model_json_schema(mode="serialization", by_alias=False)
            if self.result_model
            else None,
        )


class ApplicationRegistry:
    def __init__(self) -> None:
        self._implementations: dict[tuple[str, str], ApplicationRegistration] = {}

    def register(self, registration: ApplicationRegistration) -> None:
        identity = registration.key, registration.version
        if identity in self._implementations:
            raise ValueError(f"Application program already registered: {identity}")
        self._implementations[identity] = registration

    def get(self, key: str, version: str) -> ApplicationRegistration:
        try:
            return self._implementations[key, version]
        except KeyError as error:
            raise ValueError(f"Application program is not installed: {key}@{version}") from error

    def describe(self) -> list[ApplicationDescriptor]:
        return [self._implementations[key].descriptor() for key in sorted(self._implementations)]
