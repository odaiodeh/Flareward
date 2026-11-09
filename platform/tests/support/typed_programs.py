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

from flareward.programs.domain.models import ApplicationDefinition, ProgramDefinition
from flareward.programs.ports import ProgramRuntime
from flareward.programs.registry import ApplicationRegistration
from flareward.services.identity.domain import Identity

__runengine_contract__ = "flareward-test-typed-programs-v1"


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


APPLICATION_PROGRAMS = (
    ApplicationRegistration(
        "typed_program",
        "1",
        TypedConfig,
        typed_program,
        input_model=TypedInput,
        result_model=TypedResult,
    ),
    ApplicationRegistration(
        "numbers_program",
        "1",
        TypedConfig,
        numbers_program,
        input_model=Numbers,
        result_model=Numbers,
    ),
    ApplicationRegistration("nonfinite_program", "1", TypedConfig, nonfinite_program),
    ApplicationRegistration("model_error_program", "1", TypedConfig, model_error_program),
    ApplicationRegistration("identity_program", "1", TypedConfig, identity_program),
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
        implementation=ApplicationDefinition(
            implementation=implementation, version="1", config=config or {}
        ),
    )
