"""Compose approved feature design with the reusable Engineering Program."""

import json
from enum import StrEnum
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, JsonValue, model_validator

from lumora.elements.coding.contracts import CodingInput
from lumora.programs.composition.scope import ChildCalls
from lumora.programs.domain.models import PathBinding
from lumora.programs.ports import ChildContract, ProgramRuntime
from lumora.programs.registry import ApplicationRegistration
from plugins.adlc.programs.design import (
    AcceptanceCriteria,
    DesignOutcome,
    DesignResult,
    FeatureRequest,
)
from plugins.adlc.programs.program import (
    CompletionName,
    EngineeringInput,
    EngineeringOutcome,
    EngineeringResult,
    validate_result,
)


class CodingFeatureInput(CodingInput):
    acceptance_criteria: AcceptanceCriteria
    completion: CompletionName | None = None


class CodingFeatureOutcome(StrEnum):
    VERIFIED = "verified"
    DESIGN_UNSATISFIED = "design_unsatisfied"
    ENGINEERING_UNSATISFIED = "engineering_unsatisfied"


class CodingFeatureResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, hide_input_in_errors=True)
    outcome: CodingFeatureOutcome
    design: DesignResult
    engineering: EngineeringResult | None = None

    @model_validator(mode="after")
    def phase_outcomes_match(self) -> Self:
        if self.design.outcome != DesignOutcome.APPROVED:
            if self.engineering is not None:
                raise ValueError("Implementation requires an approved design")
            expected = CodingFeatureOutcome.DESIGN_UNSATISFIED
        elif self.engineering is None:
            raise ValueError("An approved feature result requires its Engineering outcome")
        else:
            expected = (
                CodingFeatureOutcome.VERIFIED
                if self.engineering.outcome == EngineeringOutcome.VERIFIED
                else CodingFeatureOutcome.ENGINEERING_UNSATISFIED
            )
        if self.outcome != expected:
            raise ValueError("Feature outcome must match its design and Engineering results")
        return self


class CodingFeatureConfig(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    design: str = Field(default="design", min_length=1, max_length=128)
    engineering: str = Field(default="engineering", min_length=1, max_length=128)

    @model_validator(mode="after")
    def distinct_children(self) -> Self:
        if self.design == self.engineering:
            raise ValueError("Design and Engineering must use distinct child aliases")
        return self

    def child_contracts(self) -> dict[str, ChildContract]:
        return {
            self.design: ChildContract(
                scope_schema=FeatureRequest.model_json_schema(),
                outputs={
                    name: PathBinding(path=(name,))
                    for name, field in DesignResult.model_fields.items()
                    if field.is_required()
                },
                result_model=DesignResult,
            ),
            self.engineering: ChildContract(
                scope_schema=EngineeringInput.model_json_schema(),
                outputs={
                    name: PathBinding(path=(name,))
                    for name, field in EngineeringResult.model_fields.items()
                    if field.is_required()
                },
                result_model=EngineeringResult,
            ),
        }


class CodingFeatureCoordinator:
    def __init__(self, runtime: ProgramRuntime, config: CodingFeatureConfig) -> None:
        self._runtime, self._config = runtime, config

    async def run(self, request: CodingFeatureInput) -> CodingFeatureResult:
        task = CodingInput(prompt=request.prompt, context=request.context, files=request.files)
        feature = FeatureRequest(
            task=task.model_dump(mode="json"), acceptance_criteria=request.acceptance_criteria
        )
        async with ChildCalls(self._runtime) as calls:
            _, value = await calls.call(
                self._config.design, feature.model_dump(mode="json"), key="design"
            )
            design = validate_result(DesignResult, value)
            if design.design.request != feature:
                raise ValueError("Approved design identifies a different feature request")
            if design.outcome != DesignOutcome.APPROVED:
                return CodingFeatureResult(
                    outcome=CodingFeatureOutcome.DESIGN_UNSATISFIED, design=design
                )
            approved = json.dumps(
                {
                    "design_revision": design.design.number,
                    "proposal": design.design.proposal.model_dump(mode="json"),
                    "acceptance_criteria": list(request.acceptance_criteria),
                    "approval_id": design.review.review.review_id,
                },
                ensure_ascii=False,
            )
            task = validate_result(
                CodingInput,
                {
                    "prompt": task.prompt,
                    "context": task.context + "\nApproved feature design:\n" + approved,
                    "files": [file.model_dump(mode="json") for file in task.files],
                },
            )
            _, value = await calls.call(
                self._config.engineering,
                EngineeringInput(
                    task=task.model_dump(mode="json"), completion=request.completion
                ).model_dump(mode="json"),
                key="engineering",
            )
            engineering = validate_result(EngineeringResult, value)
            if request.completion is not None and engineering.completion != request.completion:
                raise ValueError("Engineering result identifies a different completion choice")
            return CodingFeatureResult(
                outcome=CodingFeatureOutcome.VERIFIED
                if engineering.outcome == EngineeringOutcome.VERIFIED
                else CodingFeatureOutcome.ENGINEERING_UNSATISFIED,
                design=design,
                engineering=engineering,
            )


async def coding_feature(
    runtime: ProgramRuntime, inputs: JsonValue, config: BaseModel
) -> JsonValue:
    assert isinstance(config, CodingFeatureConfig)
    return (
        await CodingFeatureCoordinator(runtime, config).run(
            validate_result(CodingFeatureInput, inputs)
        )
    ).model_dump(mode="json")


APPLICATION_PROGRAMS = (
    ApplicationRegistration(
        "coding_feature",
        "1",
        CodingFeatureConfig,
        coding_feature,
        name="Design and deliver a feature",
        description="Approve an exact design before starting reusable verified Engineering",
        input_model=CodingFeatureInput,
        result_model=CodingFeatureResult,
    ),
)
