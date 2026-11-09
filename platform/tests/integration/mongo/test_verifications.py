"""Actual durable verification state and concurrent application transitions over Mongo CAS."""

import asyncio

import pytest
from support.verification import (
    VerificationClock,
    evidence_request,
    verification_authority,
    verification_policy,
    verification_request,
)

from flareward.services.identity.domain import Identity
from flareward.services.verification.access_models import VerificationActor
from flareward.services.verification.adapters.mongo.verification_repository import (
    MongoVerificationRepository,
)
from flareward.services.verification.domain.models import VerificationOutcome
from flareward.services.verification.ports import VerificationStorageError
from flareward.services.verification.service import VerificationService


async def test_records_survive_reconstruction_and_concurrent_checks_have_no_lost_updates(
    mongo_database,
):
    owner, clock = Identity.user("owner"), VerificationClock()
    policies = {"release@1": verification_policy(owner)}
    repository = MongoVerificationRepository(mongo_database)
    service = VerificationService(repository, policies, clock=clock)
    first = await service.start(verification_request(), VerificationActor(owner))
    recovered = VerificationService(
        MongoVerificationRepository(mongo_database), policies, clock=clock
    )
    assert await recovered.start(verification_request(), VerificationActor(owner)) == first
    await asyncio.gather(
        service.submit(evidence_request(first.state.plan), verification_authority(owner)),
        recovered.submit(
            evidence_request(first.state.plan, "security@1"),
            verification_authority(owner, "scanner"),
        ),
    )
    latest = await recovered.inspect(first.state.plan.plan_id, VerificationActor(owner))
    assert latest.outcome == VerificationOutcome.ACCEPTED
    assert latest.state.revision == 2 and len(latest.state.evidence) == 2
    assert not await repository.save(latest.state, expected_revision=1)


async def test_cancel_and_partial_receipts_are_durable(mongo_database):
    owner, clock = Identity.user("owner"), VerificationClock()
    repository = MongoVerificationRepository(mongo_database)
    service = VerificationService(
        repository, {"release@1": verification_policy(owner)}, clock=clock
    )
    view = await service.start(verification_request(), VerificationActor(owner))
    await service.submit(evidence_request(view.state.plan), verification_authority(owner))
    await service.cancel(view.state.plan.plan_id, VerificationActor(owner))
    restored = VerificationService(MongoVerificationRepository(mongo_database), {}, clock=clock)
    result = await restored.inspect(view.state.plan.plan_id, VerificationActor(owner))
    assert result.outcome == VerificationOutcome.CANCELLED and len(result.state.evidence) == 1


async def test_corrupted_records_fail_privately_instead_of_becoming_accepted(mongo_database):
    repository = MongoVerificationRepository(mongo_database)
    await mongo_database.program_verifications.insert_one(
        {
            "_id": "a" * 64,
            "revision": 0,
            "data": "private-corrupted-data",
        }
    )
    with pytest.raises(VerificationStorageError) as error:
        await repository.get("a" * 64)
    assert "private-corrupted-data" not in str(error.value)
