"""Acceptance requires every admitted check for an exact, immutable candidate."""

import asyncio

import pytest
from support.verification import (
    MemoryVerificationRepository,
    VerificationClock,
    evidence_request,
    verification_authority,
    verification_policy,
    verification_request,
)

from flareward.services.identity.domain import Identity
from flareward.services.verification.access_models import VerificationActor
from flareward.services.verification.domain.models import CheckVerdict, VerificationOutcome
from flareward.services.verification.ports import VerificationConflict, VerificationMissing
from flareward.services.verification.service import VerificationService


@pytest.fixture
def verification_case():
    owner, clock = Identity.user("owner"), VerificationClock()
    service = VerificationService(
        MemoryVerificationRepository(), {"release@1": verification_policy(owner)}, clock=clock
    )
    return service, owner, clock


async def test_all_checks_are_required_for_the_same_frozen_candidate(verification_case):
    service, owner, clock = verification_case
    view = await service.start(verification_request(), VerificationActor(owner))
    assert view.outcome == VerificationOutcome.PENDING
    first = await service.submit(evidence_request(view.state.plan), verification_authority(owner))
    assert first.outcome == VerificationOutcome.PENDING
    accepted = await service.submit(
        evidence_request(view.state.plan, "security@1"), verification_authority(owner, "scanner")
    )
    assert accepted.outcome == VerificationOutcome.ACCEPTED
    clock.advance(60)
    assert (
        await service.inspect(view.state.plan.plan_id, VerificationActor(owner))
    ).outcome == VerificationOutcome.ACCEPTED
    with pytest.raises(VerificationConflict):
        await service.cancel(view.state.plan.plan_id, VerificationActor(owner))


async def test_intents_and_receipts_are_idempotent_and_conflicting_changes_are_rejected(
    verification_case,
):
    service, owner, _ = verification_case
    view = await service.start(verification_request(), VerificationActor(owner))
    assert await service.start(verification_request(), VerificationActor(owner)) == view
    with pytest.raises(VerificationConflict):
        await service.start(verification_request(digest="b" * 64), VerificationActor(owner))
    receipt = evidence_request(view.state.plan)
    first = await service.submit(receipt, verification_authority(owner))
    assert await service.submit(receipt, verification_authority(owner)) == first
    for changed in (
        receipt.model_copy(update={"verdict": CheckVerdict.FAILED}),
        receipt.model_copy(update={"run_id": "another-run"}),
    ):
        with pytest.raises(VerificationConflict):
            await service.submit(changed, verification_authority(owner))


async def test_a_duplicate_receipt_is_acknowledged_after_deadline_without_admitting_new_work(
    verification_case,
):
    service, owner, clock = verification_case
    view = await service.start(verification_request(), VerificationActor(owner))
    receipt = evidence_request(view.state.plan)
    first = await service.submit(receipt, verification_authority(owner))
    clock.advance(60)
    retried = await service.submit(receipt, verification_authority(owner))
    assert retried.outcome == VerificationOutcome.EXPIRED
    assert retried.state == first.state
    with pytest.raises(VerificationConflict):
        await service.submit(
            evidence_request(view.state.plan, "security@1"),
            verification_authority(owner, "scanner"),
        )


async def test_admitted_plans_keep_their_checks_when_operator_policy_is_removed():
    owner, clock = Identity.user("owner"), VerificationClock()
    repository = MemoryVerificationRepository()
    service = VerificationService(
        repository, {"release@1": verification_policy(owner)}, clock=clock
    )
    request = verification_request()
    view = await service.start(request, VerificationActor(owner))
    restored = VerificationService(repository, {}, clock=clock)
    assert await restored.start(request, VerificationActor(owner)) == view
    await restored.submit(evidence_request(view.state.plan), verification_authority(owner))
    final = await restored.submit(
        evidence_request(view.state.plan, "security@1"), verification_authority(owner, "scanner")
    )
    assert final.outcome == VerificationOutcome.ACCEPTED
    with pytest.raises(PermissionError):
        await restored.start(verification_request(key="new-work"), VerificationActor(owner))


async def test_receipts_for_different_candidates_and_occurrences_cannot_be_reused(
    verification_case,
):
    service, owner, _ = verification_case
    old = await service.start(verification_request(), VerificationActor(owner))
    changed = await service.start(
        verification_request(key="repair", digest="b" * 64), VerificationActor(owner)
    )
    receipt = evidence_request(old.state.plan)
    with pytest.raises(VerificationConflict, match="different candidate"):
        await service.submit(
            receipt.model_copy(update={"plan_id": changed.state.plan.plan_id}),
            verification_authority(owner),
        )
    await service.submit(receipt, verification_authority(owner))
    assert (
        await service.inspect(changed.state.plan.plan_id, VerificationActor(owner))
    ).state.evidence == ()
    assert changed.outcome == VerificationOutcome.PENDING


async def test_json_boolean_integer_and_float_candidates_do_not_share_evidence(verification_case):
    service, owner, _ = verification_case
    request = verification_request()
    original = request.model_copy(
        update={"subject": request.subject.model_copy(update={"identity": {"version": 1}})}
    )
    view = await service.start(original, VerificationActor(owner))
    for value in (True, 1.0):
        changed = original.model_copy(
            update={"subject": original.subject.model_copy(update={"identity": {"version": value}})}
        )
        with pytest.raises(VerificationConflict):
            await service.start(changed, VerificationActor(owner))
        receipt = evidence_request(view.state.plan).model_copy(update={"subject": changed.subject})
        with pytest.raises(VerificationConflict):
            await service.submit(receipt, verification_authority(owner))


async def test_owners_checks_and_verifier_authorities_cannot_be_widened(verification_case):
    service, owner, _ = verification_case
    view = await service.start(verification_request(), VerificationActor(owner))
    for foreign in (Identity.user("other"), Identity.team("owner")):
        with pytest.raises(PermissionError):
            await service.start(verification_request(), VerificationActor(foreign))
        with pytest.raises(VerificationMissing):
            await service.inspect(view.state.plan.plan_id, VerificationActor(foreign))
        with pytest.raises(VerificationMissing):
            await service.submit(evidence_request(view.state.plan), verification_authority(foreign))
    with pytest.raises(PermissionError):
        await service.submit(
            evidence_request(view.state.plan), verification_authority(owner, "scanner")
        )
    with pytest.raises(PermissionError):
        await service.submit(
            evidence_request(view.state.plan, "invented@1"), verification_authority(owner)
        )


@pytest.mark.parametrize(
    "verdict,outcome",
    [
        (CheckVerdict.FAILED, VerificationOutcome.REJECTED),
        (CheckVerdict.ERROR, VerificationOutcome.ERROR),
    ],
)
async def test_failed_and_broken_checks_are_not_successful_acceptance(
    verification_case, verdict, outcome
):
    service, owner, _ = verification_case
    view = await service.start(verification_request(), VerificationActor(owner))
    result = await service.submit(
        evidence_request(view.state.plan, verdict=verdict), verification_authority(owner)
    )
    assert result.outcome == outcome


async def test_expiry_and_cancellation_fence_new_evidence(verification_case):
    service, owner, clock = verification_case
    expired = await service.start(verification_request(), VerificationActor(owner))
    cancelled = await service.start(verification_request(key="cancel"), VerificationActor(owner))
    first = await service.cancel(cancelled.state.plan.plan_id, VerificationActor(owner))
    assert first.outcome == VerificationOutcome.CANCELLED
    assert await service.cancel(cancelled.state.plan.plan_id, VerificationActor(owner)) == first
    clock.advance(60)
    assert (
        await service.inspect(expired.state.plan.plan_id, VerificationActor(owner))
    ).outcome == VerificationOutcome.EXPIRED
    for view in (expired, cancelled):
        with pytest.raises(VerificationConflict):
            await service.submit(evidence_request(view.state.plan), verification_authority(owner))


async def test_concurrent_checks_preserve_both_receipts_without_a_lost_update(verification_case):
    service, owner, _ = verification_case
    view = await service.start(verification_request(), VerificationActor(owner))
    await asyncio.gather(
        service.submit(evidence_request(view.state.plan), verification_authority(owner)),
        service.submit(
            evidence_request(view.state.plan, "security@1"),
            verification_authority(owner, "scanner"),
        ),
    )
    final = await service.inspect(view.state.plan.plan_id, VerificationActor(owner))
    assert final.outcome == VerificationOutcome.ACCEPTED and final.state.revision == 2


async def test_cancellation_racing_a_receipt_cannot_leave_acceptance_after_cancellation(
    verification_case,
):
    service, owner, _ = verification_case
    view = await service.start(verification_request(), VerificationActor(owner))
    results = await asyncio.gather(
        service.submit(evidence_request(view.state.plan), verification_authority(owner)),
        service.cancel(view.state.plan.plan_id, VerificationActor(owner)),
        return_exceptions=True,
    )
    assert all(
        not isinstance(result, Exception) or isinstance(result, VerificationConflict)
        for result in results
    )
    final = await service.inspect(view.state.plan.plan_id, VerificationActor(owner))
    assert final.outcome == VerificationOutcome.CANCELLED
    with pytest.raises(VerificationConflict):
        await service.submit(
            evidence_request(view.state.plan, "security@1"),
            verification_authority(owner, "scanner"),
        )
