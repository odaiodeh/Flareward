"""Shared registered design peer and ordinary Program definitions, without infrastructure."""

from pydantic import BaseModel, ConfigDict, JsonValue

from lumora.elements.catalog.element_registry import ElementRegistry
from lumora.executions.domain.preferences import ExecutionSelection
from lumora.programs.domain.models import CustomCoordinatorDefinition, ProgramBody, ProgramRef
from lumora.programs.ports import ProgramRuntime
from lumora.programs.registry import CoordinatorRegistration, CustomCoordinatorStrategy
from plugins.adlc.programs.design import (
    DesignProposal,
    DesignWork,
    FeatureDesignConfig,
)
from plugins.adlc.programs.reviewer import ReviewDependency
from support.review_programs import confirmation_bundle, review_body


class DesignerConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")


async def designer(runtime: ProgramRuntime, inputs: JsonValue, config: BaseModel) -> JsonValue:
    work = DesignWork.model_validate(inputs)
    plan = f"Design revision {work.attempt + 1}: implement the recorded acceptance criteria."
    if work.feedback is not None:
        plan += " Address reviewer feedback: " + work.feedback.response.model_dump_json()
    return DesignProposal(plan=plan).model_dump(mode="json")


def designer_body() -> ProgramBody:
    return ProgramBody(
        implementation=CustomCoordinatorDefinition(
            implementation="fixture_feature_designer", version="1"
        ),
        input_schema=DesignWork.model_json_schema(),
        output_schema=DesignProposal.model_json_schema(),
    )


def design_definition(
    registry: ElementRegistry,
    profile: str = "thread",
    *,
    designer: ProgramRef | ProgramBody | None = None,
    review_timeout_seconds: int = 60,
    reviewer: ProgramRef | ProgramBody | None = None,
) -> CustomCoordinatorDefinition:
    config = FeatureDesignConfig(
        review=ReviewDependency(
            policy="release@1",
            confirmation=confirmation_bundle(registry),
            execution=ExecutionSelection(profile=profile),
        ),
        max_revisions=1,
    )
    return CustomCoordinatorDefinition(
        implementation="feature_design",
        version="2",
        config=config.model_dump(mode="json"),
        children={
            "design": designer or designer_body(),
            "reviewer": reviewer
            or review_body(registry, profile, timeout_seconds=review_timeout_seconds),
        },
    )


COORDINATORS = (
    CoordinatorRegistration(
        "fixture_feature_designer",
        "1",
        DesignerConfig,
        CustomCoordinatorStrategy(designer),
        input_model=DesignWork,
        result_model=DesignProposal,
    ),
)
