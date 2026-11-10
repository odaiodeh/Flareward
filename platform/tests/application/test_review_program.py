"""Review messages are wakeups; only authoritative operation results decide a program."""

import asyncio
from unittest.mock import create_autospec

import pytest
from support.operations import operation_bundle
from support.reviews import (
    MemoryReviews,
    ReviewExecutions,
    review_actor,
    review_policy,
    review_request,
)
from support.verification import VerificationClock

from lumora.programs.ports import ProgramRuntime
from lumora.services.identity.domain import Identity
from lumora.services.reviews.contracts import SubmitReview
from lumora.services.reviews.service import ReviewService
from plugins.human_review.programs.human_review import HumanReviewConfig, human_review


@pytest.fixture
async def program_case(application):
    owner = Identity.user("owner")
    service = ReviewService(
        MemoryReviews(),
        ReviewExecutions(),
        {"release@1": review_policy(owner)},
        clock=VerificationClock(),
    )
    request = review_request()
    pending = await service.open(request, review_actor(owner))
    bundle = operation_bundle(application.elements)
    config = HumanReviewConfig(
        policy=request.policy,
        template=request.specification.model_dump(mode="json", exclude={"subject"}),
        opener=bundle,
        inspection=bundle,
        max_checks=2,
    )
    runtime = create_autospec(ProgramRuntime, instance=True)
    runtime.execution_id = request.execution_id
    return owner, service, request, pending, config, runtime


@pytest.mark.parametrize("resolved", [True, False])
async def test_forged_wakeups_and_timeouts_never_replace_authoritative_decisions(
    program_case, resolved
):
    owner, service, request, pending, config, runtime = program_case
    decided = await service.respond(
        pending.review_id,
        SubmitReview(
            key="reject", expected_revision=0, decision="reject", data={"feedback": "Needs changes"}
        ),
        Identity.user("reviewer"),
    )
    runtime.invoke_element.side_effect = [
        pending.model_dump(mode="json"),
        pending.model_dump(mode="json"),
        (decided if resolved else pending).model_dump(mode="json"),
    ]
    runtime.receive.side_effect = [{"decision": "approve"}, TimeoutError()]
    output = await human_review(runtime, request.specification.subject, config)
    assert output["reason"] == ("resolved" if resolved else "check_limit")
    assert output["review"]["status"] == ("decided" if resolved else "pending")
    assert output["review"]["response"] == (
        decided.response.model_dump(mode="json") if resolved else None
    )
    assert runtime.receive.await_count == 2
    assert [call.kwargs["key"] for call in runtime.invoke_element.await_args_list] == [
        "open-review",
        "inspect-review-0",
        "inspect-review-1",
    ]


async def test_program_cancellation_propagates_without_fabricating_a_response(program_case):
    owner, service, request, pending, config, runtime = program_case
    runtime.invoke_element.return_value = pending.model_dump(mode="json")
    runtime.receive.side_effect = asyncio.CancelledError()
    with pytest.raises(asyncio.CancelledError):
        await human_review(runtime, request.specification.subject, config)
    assert runtime.invoke_element.await_count == 1
    assert (await service.inspect(pending.review_id, review_actor(owner))).response is None


async def test_an_inspection_cannot_substitute_another_review_occurrence(program_case):
    owner, service, request, pending, config, runtime = program_case
    runtime.invoke_element.side_effect = [
        pending.model_dump(mode="json"),
        pending.model_copy(update={"review_id": "f" * 64}).model_dump(mode="json"),
    ]
    with pytest.raises(ValueError, match="different occurrence"):
        await human_review(runtime, request.specification.subject, config)
