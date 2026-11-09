"""Versioned feature proposals with bounded revision and durable human review."""

from enum import StrEnum
from typing import Annotated, Self

from pydantic import BaseModel, ConfigDict, Field, JsonValue, model_validator

from flareward.programs.composition.scope import ChildCalls
from flareward.programs.domain.models import PathBinding
from flareward.programs.ports import ChildContract, ProgramRuntime
from flareward.programs.registry import ApplicationRegistration
from flareward.services.reviews.domain.models import ReviewDecision, ReviewResponse, ReviewStatus
from flareward.services.verification.domain.models import VerificationSubject
from plugins.adlc.programs.program import (
    AttemptRuntime,
    require_service_operation,
    validate_result,
)
from plugins.human_review.programs.human_review import (
    HumanReviewConfig,
    HumanReviewResult,
    human_review,
)

type AcceptanceCriteria = Annotated[
    tuple[Annotated[str, Field(min_length=1, max_length=2048)], ...],
    Field(min_length=1, max_length=32),
]


class FeatureRequest[Task = JsonValue](BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, hide_input_in_errors=True)
    task: Task
    acceptance_criteria: AcceptanceCriteria


class DesignProposal(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, hide_input_in_errors=True)
    plan: str = Field(min_length=1, max_length=32_768)
    references: tuple[VerificationSubject, ...] = Field(default=(), max_length=16)


class DesignRevision(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, hide_input_in_errors=True)
    number: int = Field(ge=1)
    request: FeatureRequest
    proposal: DesignProposal


class DesignFeedback(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, hide_input_in_errors=True)
    design: DesignRevision
    response: ReviewResponse


class DesignWork[Task = JsonValue](BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, hide_input_in_errors=True)
    request: FeatureRequest[Task]
    attempt: int = Field(ge=0)
    feedback: DesignFeedback | None = None


class DesignOutcome(StrEnum):
    APPROVED = "approved"
    REVISIONS_EXHAUSTED = "revisions_exhausted"
    REVIEW_UNRESOLVED = "review_unresolved"
    REVIEW_CLOSED = "review_closed"


class DesignResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, hide_input_in_errors=True)
    outcome: DesignOutcome
    design: DesignRevision
    review: HumanReviewResult

    @model_validator(mode="after")
    def identifies_reviewed_design(self) -> Self:
        record = self.review.review
        expected_review = record.specification.model_copy(
            update={"subject": self.design.model_dump(mode="json")}
        )
        if record.specification.fingerprint != expected_review.fingerprint:
            raise ValueError("Design result must identify the exact reviewed revision")
        if record.status == ReviewStatus.DECIDED and record.response is not None:
            expected = (
                DesignOutcome.APPROVED
                if record.response.decision == ReviewDecision.APPROVE
                else DesignOutcome.REVISIONS_EXHAUSTED
            )
        elif record.status == ReviewStatus.PENDING:
            expected = DesignOutcome.REVIEW_UNRESOLVED
        else:
            expected = DesignOutcome.REVIEW_CLOSED
        if self.outcome != expected:
            raise ValueError("Design outcome must match its recorded review")
        return self


class FeatureDesignConfig(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    designer: str = Field(default="design", min_length=1, max_length=128)
    max_revisions: int = Field(default=2, ge=0, le=20)
    review: HumanReviewConfig

    @model_validator(mode="after")
    def validate_authority(self) -> Self:
        require_service_operation(self.review.opener, "open_human_review", "review_service")
        require_service_operation(self.review.inspection, "inspect_human_review", "review_service")
        return self

    def child_contracts(self) -> dict[str, ChildContract]:
        return {
            self.designer: ChildContract(
                scope_schema=DesignWork.model_json_schema(),
                outputs={"plan": PathBinding(path=("plan",))},
                result_model=DesignProposal,
            )
        }


class FeatureDesignCoordinator:
    def __init__(self, runtime: ProgramRuntime, config: FeatureDesignConfig) -> None:
        self._runtime, self._config = runtime, config

    async def run(self, request: FeatureRequest) -> DesignResult:
        feedback: DesignFeedback | None = None
        async with ChildCalls(self._runtime) as calls:
            for attempt in range(self._config.max_revisions + 1):
                work = DesignWork(request=request, attempt=attempt, feedback=feedback)
                _, value = await calls.call(
                    self._config.designer, work.model_dump(mode="json"), key=f"design-{attempt}"
                )
                design = DesignRevision(
                    number=attempt + 1,
                    request=request,
                    proposal=validate_result(DesignProposal, value),
                )
                review = validate_result(
                    HumanReviewResult,
                    await human_review(
                        AttemptRuntime(self._runtime, attempt),
                        design.model_dump(mode="json"),
                        self._config.review,
                    ),
                )
                record = review.review
                if record.status == ReviewStatus.DECIDED and record.response is not None:
                    if record.response.decision == ReviewDecision.APPROVE:
                        outcome = DesignOutcome.APPROVED
                    elif attempt == self._config.max_revisions:
                        outcome = DesignOutcome.REVISIONS_EXHAUSTED
                    else:
                        feedback = DesignFeedback(design=design, response=record.response)
                        continue
                elif record.status == ReviewStatus.PENDING:
                    outcome = DesignOutcome.REVIEW_UNRESOLVED
                else:
                    outcome = DesignOutcome.REVIEW_CLOSED
                return DesignResult(outcome=outcome, design=design, review=review)
        raise AssertionError("Feature design requires at least one proposal")


async def feature_design(
    runtime: ProgramRuntime, inputs: JsonValue, config: BaseModel
) -> JsonValue:
    assert isinstance(config, FeatureDesignConfig)
    return (
        await FeatureDesignCoordinator(runtime, config).run(validate_result(FeatureRequest, inputs))
    ).model_dump(mode="json")


APPLICATION_PROGRAMS = (
    ApplicationRegistration(
        "feature_design",
        "1",
        FeatureDesignConfig,
        feature_design,
        name="Feature design and approval",
        description="Propose, review and revise an exact feature design before implementation",
        input_model=FeatureRequest,
        result_model=DesignResult,
    ),
)
