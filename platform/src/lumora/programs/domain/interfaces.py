"""Portable Program invocation interfaces, independent of installed Python models."""

from pydantic import Field, JsonValue

from lumora.models import Model
from lumora.programs.domain.bindings import Bindings, Projection


class CoordinatorIdentity(Model):
    key: str = Field(min_length=1)
    version: str = Field(min_length=1)


class ProgramSchemas(Model):
    """Configuration-resolved raw-input and serialized-output constraints."""

    input_schema: dict[str, JsonValue] | None = None
    output_schema: dict[str, JsonValue] | None = None


class DependencyInterface(Model):
    """Caller-owned request projection and consumed-result contract, without live models."""

    inputs: Projection | None = None
    scope_schema: dict[str, JsonValue] | None = None
    outputs: Bindings = Field(default_factory=dict)
    result_model_schema: dict[str, JsonValue] | None = None
    result_schema: dict[str, JsonValue] | None = None


class ProgramInterface(Model):
    """Separate raw intent, normalization and serialized-result constraints.

    Each schema is a complete document with its own reference scope. Optional
    normalization schemas describe the canonical values passed to/returned from
    installed behavior; they do not replace raw-input admission or Python validators.
    The coordinator identity versions that deterministic normalization behavior.
    """

    dependencies: dict[str, DependencyInterface] = Field(default_factory=dict)
    configured: ProgramSchemas | None = None
    coordinator: CoordinatorIdentity
    input_schema: dict[str, JsonValue]
    input_model_schema: dict[str, JsonValue] | None = None
    normalized_input_schema: dict[str, JsonValue] | None = None
    output_schema: dict[str, JsonValue]
    output_model_schema: dict[str, JsonValue] | None = None
    normalized_output_schema: dict[str, JsonValue] | None = None
    children: dict[str, ProgramInterface] = Field(default_factory=dict)

    @property
    def input_schemas(self) -> tuple[dict[str, JsonValue], ...]:
        extra = self.configured.input_schema if self.configured is not None else None
        return (self.input_schema,) if extra is None else (self.input_schema, extra)

    @property
    def output_schemas(self) -> tuple[dict[str, JsonValue], ...]:
        extra = self.configured.output_schema if self.configured is not None else None
        return (self.output_schema,) if extra is None else (self.output_schema, extra)

    def at(self, path: tuple[str, ...]) -> ProgramInterface:
        interface = self
        for name in path:
            try:
                interface = interface.children[name]
            except KeyError:
                raise ValueError("Interface path does not identify an owned Program body") from None
        return interface
