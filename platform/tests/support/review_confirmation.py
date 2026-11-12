"""A normal coordinator consumes a replaceable reviewer and confirms persisted evidence."""

from pydantic import BaseModel, ConfigDict, JsonValue

from lumora.executions.domain.preferences import ExecutionSelection
from lumora.programs.composition.scope import ChildCalls
from lumora.programs.ports import ProgramRuntime
from lumora.programs.registry import CoordinatorRegistration, CustomCoordinatorStrategy
from lumora.resources.domain.bundles import ElementBundle
from lumora.services.reviews.contracts import ConfirmReview
from lumora.services.reviews.domain.models import ReviewRecord
from lumora.services.reviews.domain.results import HumanReviewResult


class ConfirmationConfig(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    confirmation: ElementBundle
    execution: ExecutionSelection


async def reviewed_work(runtime: ProgramRuntime, inputs: JsonValue, config: BaseModel) -> JsonValue:
    assert isinstance(config, ConfirmationConfig)
    async with ChildCalls(runtime) as calls:
        child_id, returned = await calls.call("reviewer", inputs, key="review")
    proposal = HumanReviewResult.model_validate(returned)
    request = ConfirmReview(
        review_id=proposal.review.review_id,
        within_execution_id=child_id,
        policy="release@1",
        subject=inputs,
    )
    return await runtime.invoke_element(
        config.confirmation,
        request.model_dump(mode="json"),
        key="confirm",
        execution=config.execution,
    )


COORDINATORS = (
    CoordinatorRegistration(
        "fixture_review_confirmation",
        "1",
        ConfirmationConfig,
        CustomCoordinatorStrategy(reviewed_work),
        result_model=ReviewRecord,
    ),
)
