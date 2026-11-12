"""Installed typed Program implementations shared by application, API and native tests."""

from typing import Annotated

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    JsonValue,
    RootModel,
    computed_field,
    field_validator,
)

from lumora.programs.domain.interfaces import ProgramSchemas
from lumora.programs.domain.models import CustomCoordinatorDefinition, ProgramDefinition
from lumora.programs.ports import ProgramRuntime
from lumora.programs.registry import CoordinatorRegistration, CustomCoordinatorStrategy
from lumora.services.identity.domain import Identity

__runengine_contract__ = "lumora-test-typed-programs-v1"


class TypedConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    multiplier: int = Field(default=2, ge=1)
    invalid_result: bool = False


class TypedInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    amount: int = Field(ge=1, alias="amountAlias")
    label: str
    tags: tuple[str, ...] = ()

    @field_validator("label")
    @classmethod
    def allowed_label(cls, value: str) -> str:
        if value.startswith("private-"):
            raise ValueError("Rejected label: " + value)
        return value


class TypedResult(BaseModel):
    model_config = ConfigDict(extra="forbid")
    total: int = Field(ge=1)
    label: str = Field(serialization_alias="wireLabel")
    tags: tuple[str, ...]

    @computed_field
    def summary(self) -> str:
        return f"{self.label}:{self.total}"


class Numbers(RootModel[list[Annotated[int, Field(ge=0)]]]):
    pass


async def typed_program(runtime: ProgramRuntime, inputs: JsonValue, config: BaseModel) -> JsonValue:
    assert isinstance(config, TypedConfig) and isinstance(inputs, dict)
    amount, label, tags = inputs["amount"], inputs["label"], inputs["tags"]
    assert isinstance(amount, int) and isinstance(label, str) and isinstance(tags, list)
    await runtime.sleep(0.001)
    return {
        "total": -1 if config.invalid_result else amount * config.multiplier,
        "label": label,
        "tags": tags,
    }


async def numbers_program(
    runtime: ProgramRuntime, inputs: JsonValue, config: BaseModel
) -> JsonValue:
    assert isinstance(inputs, list) and isinstance(config, TypedConfig)
    await runtime.sleep(0.001)
    result: list[JsonValue] = []
    for value in inputs:
        assert isinstance(value, int)
        result.append(value * config.multiplier)
    return result


async def nonfinite_program(
    runtime: ProgramRuntime, inputs: JsonValue, config: BaseModel
) -> JsonValue:
    await runtime.sleep(0.001)
    return float("nan")


async def model_error_program(
    runtime: ProgramRuntime, inputs: JsonValue, config: BaseModel
) -> JsonValue:
    await runtime.sleep(0.001)
    TypedResult.model_validate({"total": -1, "label": "private-model-value", "tags": []})
    return {}


async def identity_program(
    runtime: ProgramRuntime, inputs: JsonValue, config: BaseModel
) -> JsonValue:
    await runtime.sleep(0.001)
    return inputs


class BoundedEchoConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    limit: int = Field(default=5, ge=1)
    output_limit: int = Field(default=5, ge=1)

    def program_interface(self) -> ProgramSchemas:
        return ProgramSchemas(
            input_schema={
                "type": "object",
                "required": ["value"],
                "properties": {"value": {"type": "integer", "maximum": self.limit}},
            },
            output_schema={
                "type": "object",
                "required": ["value"],
                "properties": {"value": {"type": "integer", "maximum": self.output_limit}},
            },
        )


COORDINATORS = (
    CoordinatorRegistration(
        "typed_program",
        "1",
        TypedConfig,
        CustomCoordinatorStrategy(typed_program),
        input_model=TypedInput,
        result_model=TypedResult,
    ),
    CoordinatorRegistration(
        "numbers_program",
        "1",
        TypedConfig,
        CustomCoordinatorStrategy(numbers_program),
        input_model=Numbers,
        result_model=Numbers,
    ),
    CoordinatorRegistration(
        "nonfinite_program", "1", TypedConfig, CustomCoordinatorStrategy(nonfinite_program)
    ),
    CoordinatorRegistration(
        "model_error_program", "1", TypedConfig, CustomCoordinatorStrategy(model_error_program)
    ),
    CoordinatorRegistration(
        "identity_program", "1", TypedConfig, CustomCoordinatorStrategy(identity_program)
    ),
    CoordinatorRegistration(
        "bounded_echo", "1", BoundedEchoConfig, CustomCoordinatorStrategy(identity_program)
    ),
)


def definition(
    owner: Identity,
    *,
    implementation: str = "typed_program",
    config: dict[str, JsonValue] | None = None,
) -> ProgramDefinition:
    return ProgramDefinition(
        program_id=implementation,
        name=implementation,
        owner=owner,
        implementation=CustomCoordinatorDefinition(
            implementation=implementation, version="1", config=config or {}
        ),
    )
