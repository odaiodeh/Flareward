"""Shared registered design peer and ordinary Program definitions, without infrastructure."""

from pydantic import BaseModel, ConfigDict, JsonValue

from lumora.elements.catalog.element_registry import ElementRegistry
from lumora.programs.domain.models import ApplicationDefinition, ProgramBody, ProgramRef
from lumora.programs.ports import ProgramRuntime
from lumora.programs.registry import ApplicationRegistration
from plugins.adlc.programs.design import (
    DesignProposal,
    DesignWork,
    FeatureDesignConfig,
)
from support.review_programs import review_definition


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
        implementation=ApplicationDefinition(
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
) -> ApplicationDefinition:
    config = FeatureDesignConfig(
        review=review_definition(registry, profile, timeout_seconds=review_timeout_seconds).config,
        max_revisions=1,
    )
    return ApplicationDefinition(
        implementation="feature_design",
        version="1",
        config=config.model_dump(mode="json"),
        children={"design": designer or designer_body()},
    )


APPLICATION_PROGRAMS = (
    ApplicationRegistration(
        "fixture_feature_designer",
        "1",
        DesignerConfig,
        designer,
        input_model=DesignWork,
        result_model=DesignProposal,
    ),
)
