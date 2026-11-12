"""Durable review coordination uses invoked effects and native messages/timeouts only."""

from pydantic import BaseModel, ConfigDict, Field, JsonValue, ValidationError

from lumora.executions.domain.preferences import ExecutionSelection
from lumora.programs.ports import ProgramRuntime
from lumora.programs.registry import CoordinatorRegistration, CustomCoordinatorStrategy
from lumora.resources.domain.bundles import ElementBundle
from lumora.services.reviews.contracts import ReviewSettings, ValidatedReviewTemplate
from lumora.services.reviews.domain.models import ReviewRecord, ReviewStatus
from lumora.services.reviews.domain.results import HumanReviewResult, ReviewWaitReason
from plugins.human_review.elements.operations import RequestReview


class HumanReviewConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    policy: str = Field(min_length=1, max_length=128)
    template: ValidatedReviewTemplate
    opener: ElementBundle
    inspection: ElementBundle
    execution: ExecutionSelection = Field(default_factory=ExecutionSelection)
    reconcile_seconds: float = Field(default=30, ge=0.1, le=300, allow_inf_nan=False)
    max_checks: int = Field(default=10_000, ge=1, le=100_000)


def review_result(value: JsonValue) -> ReviewRecord:
    try:
        return ReviewRecord.model_validate(value)
    except ValidationError:
        raise ValueError("Review effect result violates its contract") from None


async def human_review(runtime: ProgramRuntime, inputs: JsonValue, config: BaseModel) -> JsonValue:
    assert isinstance(config, HumanReviewConfig)
    specification = ReviewSettings.model_validate(
        {**config.template.model_dump(mode="json"), "subject": inputs}
    )
    opened = review_result(
        await runtime.invoke_element(
            config.opener,
            RequestReview(policy=config.policy, specification=specification).model_dump(
                mode="json"
            ),
            key="open-review",
            execution=config.execution,
        )
    )
    if (
        opened.specification.fingerprint != specification.fingerprint
        or opened.execution_id != runtime.execution_id
        or opened.policy != config.policy
    ):
        raise ValueError("Review effect identifies a different occurrence")
    current = opened
    for index in range(config.max_checks):
        if current.status != ReviewStatus.PENDING:
            return HumanReviewResult(review=current, reason=ReviewWaitReason.RESOLVED).model_dump(
                mode="json"
            )
        try:
            await runtime.receive(opened.message_name, timeout=config.reconcile_seconds)
        except TimeoutError:
            pass
        current = review_result(
            await runtime.invoke_element(
                config.inspection,
                {"review_id": opened.review_id},
                key=f"inspect-review-{index}",
                execution=config.execution,
            )
        )
        if (
            current.review_id != opened.review_id
            or current.specification.fingerprint != specification.fingerprint
            or current.execution_id != runtime.execution_id
        ):
            raise ValueError("Review inspection identifies a different occurrence")
        if current.status != ReviewStatus.PENDING:
            return HumanReviewResult(review=current, reason=ReviewWaitReason.RESOLVED).model_dump(
                mode="json"
            )
    return HumanReviewResult(review=current, reason=ReviewWaitReason.CHECK_LIMIT).model_dump(
        mode="json"
    )


COORDINATORS = (
    CoordinatorRegistration(
        "human_review",
        "1",
        HumanReviewConfig,
        CustomCoordinatorStrategy(human_review),
        result_model=HumanReviewResult,
    ),
)
