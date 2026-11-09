"""Typed review policy, exact occurrence identity, durable decisions and delivery recovery."""

import asyncio

import pytest
from support.reviews import (
    MemoryReviews,
    ReviewExecutions,
    review_actor,
    review_policy,
    review_request,
)
from support.verification import VerificationClock

from flareward.services.identity.domain import Identity
from flareward.services.reviews.access import ReviewActor
from flareward.services.reviews.contracts import CloseReview, ReviewSettings, SubmitReview
from flareward.services.reviews.domain.models import ReviewDecision, ReviewStatus
from flareward.services.reviews.ports import ReviewConflict, ReviewMissing
from flareward.services.reviews.service import ReviewService


@pytest.fixture
def scenario():
    owner, clock = Identity.user("owner"), VerificationClock()
    records, executions = MemoryReviews(), ReviewExecutions()
    service = ReviewService(records, executions, {"release@1": review_policy(owner)}, clock=clock)
    return owner, clock, records, executions, service


async def test_concurrent_identical_response_is_durable_and_conflicting_data_cannot_replace_it(
    scenario,
):
    owner, clock, records, executions, service = scenario
    review = await service.open(review_request(), review_actor(owner))
    response = SubmitReview(
        key="response-1",
        expected_revision=0,
        decision=ReviewDecision.APPROVE,
        data={"feedback": "Checks reviewed"},
    )
    values = await asyncio.gather(
        *(service.respond(review.review_id, response, Identity.user("reviewer")) for _ in range(10))
    )
    assert all(value.status == ReviewStatus.DECIDED for value in values)
    assert all(value.response.issued_by.id == "reviewer" for value in values)
    recovered = ReviewService(records, executions, {}, clock=clock)
    assert (
        await recovered.respond(review.review_id, response, Identity.user("reviewer"))
    ).response == values[0].response
    with pytest.raises(ReviewConflict):
        await service.respond(
            review.review_id,
            response.model_copy(update={"decision": ReviewDecision.REJECT}),
            Identity.user("reviewer"),
        )
    with pytest.raises(ReviewConflict):
        await service.respond(
            review.review_id,
            response.model_copy(update={"data": {"feedback": "Different work"}}),
            Identity.user("reviewer"),
        )


async def test_owner_and_workflow_scope_do_not_grant_human_reviewer_authority(scenario):
    owner, _, _, _, service = scenario
    review = await service.open(review_request(), review_actor(owner))
    response = SubmitReview(
        key="response",
        expected_revision=0,
        decision=ReviewDecision.APPROVE,
        data={"feedback": "review"},
    )
    with pytest.raises(ReviewMissing):
        await service.respond(review.review_id, response, owner)
    with pytest.raises(ReviewMissing):
        await service.inspect(review.review_id, ReviewActor(Identity.user("other")))
    actor = review_actor(owner)
    wrong_root = ReviewActor(
        owner, actor.scope.model_copy(update={"root_execution_id": "other-root"})
    )
    with pytest.raises(ReviewMissing):
        await service.inspect(review.review_id, wrong_root)
    assert len(await service.inbox(Identity.user("reviewer"))) == 1
    assert await service.inbox(owner) == []
    assert (await service.for_execution("root", owner))[0].review_id == review.review_id
    assert await service.for_execution("root", Identity.user("other")) == []
    assert await service.for_execution("different-root", owner) == []


@pytest.mark.parametrize("mode", ["expired", "cancelled", "superseded"])
async def test_closed_or_stale_review_never_accepts_late_decisions(scenario, mode):
    owner, clock, _, executions, service = scenario
    actor = review_actor(owner)
    review = await service.open(review_request(), actor)
    if mode == "expired":
        clock.advance(61)
    elif mode == "cancelled":
        executions.executions.clear()
    else:
        clock.advance(1)
        replacement = await service.open(review_request("new-occurrence"), actor)
        await service.close(
            CloseReview(
                review_id=review.review_id, expected_revision=0, superseded_by=replacement.review_id
            ),
            actor,
        )
    response = SubmitReview(
        key="response",
        expected_revision=0,
        decision=ReviewDecision.APPROVE,
        data={"feedback": "late"},
    )
    with pytest.raises(ReviewConflict):
        await service.respond(review.review_id, response, Identity.user("reviewer"))
    current = await service.inspect(review.review_id, actor)
    assert current.status.value == mode and current.response is None


async def test_lost_wakeup_ack_and_delivery_ack_keep_the_original_decision(scenario):
    owner, _, records, executions, service = scenario
    review = await service.open(review_request(), review_actor(owner))
    await service.respond(
        review.review_id,
        SubmitReview(
            key="response",
            expected_revision=0,
            decision=ReviewDecision.REJECT,
            data={"feedback": "Needs work"},
        ),
        Identity.user("reviewer"),
    )
    executions.lose_ack = True
    await service.reconcile()
    assert (await records.get(review.review_id)).delivery_pending
    executions.lose_ack = False
    records.fail_delivery_ack = True
    await service.reconcile()
    await service.reconcile()
    assert (await records.get(review.review_id)).delivery_pending
    records.fail_delivery_ack = False
    await service.reconcile()
    await service.reconcile()
    saved = await records.get(review.review_id)
    assert saved.status == ReviewStatus.DECIDED and saved.response.decision == ReviewDecision.REJECT
    assert not saved.delivery_pending and len(executions.messages) >= 2


async def test_schema_validation_and_exact_subject_identity_precede_acceptance(scenario):
    owner, _, _, _, service = scenario
    actor = review_actor(owner)
    request = review_request()
    review = await service.open(request, actor)
    with pytest.raises(ValueError, match="does not match"):
        await service.respond(
            review.review_id,
            SubmitReview(key="bad", expected_revision=0, decision=ReviewDecision.APPROVE, data={}),
            Identity.user("reviewer"),
        )
    changed = request.model_copy(
        update={
            "specification": request.specification.model_copy(
                update={"subject": {"candidate": "different"}}
            )
        }
    )
    with pytest.raises(ReviewConflict):
        await service.open(changed, actor)
    assert (await service.inspect(review.review_id, actor)).status == ReviewStatus.PENDING


@pytest.mark.parametrize(
    "schema",
    [
        {"$ref": "https://example.test/schema"},
        {"type": "invalid"},
        {"properties": {"value": {"pattern": "(a+)+$"}}},
        {"$ref": "#/$defs/missing"},
        {"$ref": "#/metadata", "metadata": {"pattern": "(a+)+$"}},
        {"$ref": "#/metadata", "metadata": {"$ref": "https://example.test/schema"}},
        {"$ref": "#/metadata", "metadata": {"type": "invalid"}},
        {"$schema": "https://example.test/unsupported-dialect"},
        {"$id": "https://example.test/resource", "type": "string"},
    ],
)
def test_invalid_or_external_schema_is_rejected_before_publication(schema):
    with pytest.raises(ValueError):
        ReviewSettings(prompt="Review", subject={}, response_schema=schema)


def test_schema_property_names_and_local_definitions_are_not_treated_as_keywords():
    ReviewSettings(
        prompt="Review",
        subject={},
        response_schema={
            "type": "object",
            "properties": {"pattern": {"$ref": "#/$defs/feedback"}},
            "$defs": {"feedback": {"type": "string"}},
        },
    )
