"""Installed coordinator configuration shapes shared by save and native API tests."""

from typing import Annotated, Literal

from pydantic import AliasChoices, AliasPath, BaseModel, ConfigDict, Field, JsonValue

from lumora.executions.domain.preferences import ExecutionSelection
from lumora.programs.ports import ProgramRuntime
from lumora.programs.registry import CoordinatorRegistration, CustomCoordinatorStrategy
from lumora.resources.domain.bundles import ElementBundle

__runengine_contract__ = "lumora-test-configuration-resources-v1"


class BundleStage(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kind: Literal["operation"] = "operation"
    bundle: ElementBundle = Field(
        validation_alias=AliasChoices("capability", AliasPath("selected", "bundle"))
    )


class EmptyStage(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kind: Literal["empty"]


class BundleConfiguration(BaseModel):
    model_config = ConfigDict(extra="forbid")
    stages: list[BundleStage] = Field(default_factory=list)
    roles: dict[str, BundleStage] = Field(default_factory=dict)
    variant: Annotated[BundleStage | EmptyStage, Field(discriminator="kind")] | None = None
    optional: ElementBundle | None = None
    metadata: dict[str, JsonValue] = Field(default_factory=dict)
    execution: ExecutionSelection = Field(default_factory=ExecutionSelection)


async def configured_resource(
    runtime: ProgramRuntime, inputs: JsonValue, config: BaseModel
) -> JsonValue:
    assert isinstance(config, BundleConfiguration)
    assert isinstance(inputs, dict)
    result = await runtime.invoke_element(
        config.stages[0].bundle,
        {"text": inputs["name"]},
        key="configured",
        execution=config.execution,
    )
    assert isinstance(result, dict)
    return {"answer": result["text"]}


COORDINATORS = (
    CoordinatorRegistration(
        "configured_resource",
        "1",
        BundleConfiguration,
        CustomCoordinatorStrategy(configured_resource),
    ),
)
