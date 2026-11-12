"""Invoke a replaceable reviewer and consume only confirmed persisted evidence."""

from typing import Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from lumora.executions.domain.preferences import ExecutionSelection
from lumora.programs.composition.scope import ChildCalls
from lumora.programs.domain.bindings import PathBinding
from lumora.programs.ports import ChildContract, ProgramRuntime
from lumora.resources.domain.bundles import ElementBundle
from lumora.services.reviews.contracts import ConfirmReview
from lumora.services.reviews.domain.models import ReviewRecord
from lumora.services.reviews.domain.results import HumanReviewResult
from plugins.adlc.programs.contracts import require_service_operation, validate_result


class ReviewDependency(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, hide_input_in_errors=True)
    program: str = Field(default="reviewer", min_length=1, max_length=128)
    policy: str = Field(min_length=1, max_length=128)
    confirmation: ElementBundle
    execution: ExecutionSelection = Field(default_factory=ExecutionSelection)

    @model_validator(mode="after")
    def validate_authority(self) -> Self:
        require_service_operation(self.confirmation, "confirm_human_review", "review_service")
        return self

    def contract(self, subject: type[BaseModel]) -> ChildContract:
        return ChildContract(
            scope_schema=subject.model_json_schema(),
            outputs={
                "review": PathBinding(path=("review",)),
                "reason": PathBinding(path=("reason",)),
            },
            result_model=HumanReviewResult,
        )


class Reviewer:
    def __init__(self, runtime: ProgramRuntime, dependency: ReviewDependency) -> None:
        self._runtime, self._dependency = runtime, dependency

    async def run(self, calls: ChildCalls, subject: BaseModel, *, key: str) -> HumanReviewResult:
        value = subject.model_dump(mode="json")
        execution_id, returned = await calls.call(self._dependency.program, value, key=key)
        proposed = validate_result(HumanReviewResult, returned)
        request = ConfirmReview(
            review_id=proposed.review.review_id,
            within_execution_id=execution_id,
            policy=self._dependency.policy,
            subject=value,
        )
        confirmed = validate_result(
            ReviewRecord,
            await self._runtime.invoke_element(
                self._dependency.confirmation,
                request.model_dump(mode="json"),
                key=f"{key}-confirm",
                execution=self._dependency.execution,
            ),
        )
        expected = confirmed.specification.model_copy(update={"subject": value})
        if (
            confirmed.review_id != request.review_id
            or confirmed.policy != request.policy
            or confirmed.specification.fingerprint != expected.fingerprint
        ):
            raise ValueError("Review confirmation identifies different work")
        return HumanReviewResult(review=confirmed, reason=proposed.reason)
