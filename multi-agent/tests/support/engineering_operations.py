"""Deterministic intake, CI and validation adapters for the delivery scenario."""

from enum import StrEnum

from mas.application.elements.factory import BaseFactory
from mas.application.elements.operation import BaseOperation, OperationContext
from mas.application.elements.specification import BaseElementSpec
from mas.core.enums import ResourceCategory
from pydantic import BaseModel, ConfigDict, JsonValue


class Stage(StrEnum):
    JIRA = "jira"
    CI = "ci"
    DEPLOYMENT_VALIDATION = "deployment_validation"


class StageConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    stage: Stage


class StageData(BaseModel):
    model_config = ConfigDict(extra="forbid")
    data: JsonValue


class StageOperation(BaseOperation[StageData, StageData]):
    def __init__(self, stage: Stage) -> None:
        self._stage = stage

    async def execute(self, request: StageData, context: OperationContext) -> StageData:
        if self._stage != Stage.JIRA and (
            not isinstance(request.data, dict) or request.data.get("outcome") != "verified"
        ):
            raise ValueError("Delivery requires verified Engineering work")
        return request


class StageFactory(BaseFactory[StageConfig, StageOperation]):
    def accepts(self, cfg: StageConfig, element_type: str) -> bool:
        return element_type == "fixture_delivery_stage"

    def create(self, cfg: StageConfig, **dependencies: object) -> StageOperation:
        return StageOperation(cfg.stage)


class StageSpec(BaseElementSpec):
    category = ResourceCategory.OPERATION
    type_key = "fixture_delivery_stage"
    name = "Deterministic delivery stage"
    description = "Test-only intake, CI and deployment-validation peer"
    config_schema = StageConfig
    factory_cls = StageFactory
    input_schema = StageData
    result_schema = StageData


ELEMENT_SPECIFICATIONS = (StageSpec,)
