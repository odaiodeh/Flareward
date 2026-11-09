"""Persisted retirement covers fixed grants and cannot invalidate a renewed lease."""

import asyncio
from datetime import UTC, datetime, timedelta

import pytest
from support.credential_renewals import RenewalCase
from support.verification import VerificationClock

from flareward.services.reviews.adapters.mongo.reviews import MongoReviewAccessRepository
from flareward.services.verification.adapters.mongo.verification_access import (
    MongoVerificationAccessRepository,
)


@pytest.mark.parametrize("purpose", ["review", "verification"])
async def test_fixed_grant_retirement_is_persisted_and_pending_roots_are_preserved(
    mongo_database, purpose
):
    reviews = MongoReviewAccessRepository(mongo_database)
    verifications = MongoVerificationAccessRepository(mongo_database)
    await reviews.initialize()
    await verifications.initialize()
    case = await RenewalCase.create(
        purpose,
        clock=VerificationClock(now=datetime.now(UTC)),
        review_repository=reviews,
        verification_repository=verifications,
        renewable=False,
    )
    case.authority.live = False
    await case.service.reconcile()
    assert (await case.repository.get(case.grant.grant_id)).grant == case.grant
    case.authority.ended = True
    await case.service.reconcile()
    stored = await case.repository.get(case.grant.grant_id)
    assert stored.grant.revoked
    assert stored.grant.model_copy(update={"revoked": False}) == case.grant
    assert not await case.repository.pending(after="", limit=100)


@pytest.mark.parametrize("purpose", ["review", "verification"])
async def test_retirement_fences_both_a_renewed_snapshot_and_a_fast_application_clock(
    mongo_database, purpose
):
    reviews = MongoReviewAccessRepository(mongo_database)
    verifications = MongoVerificationAccessRepository(mongo_database)
    await reviews.initialize()
    await verifications.initialize()
    case = await RenewalCase.create(
        purpose,
        clock=VerificationClock(now=datetime.now(UTC) - timedelta(seconds=57)),
        review_repository=reviews,
        verification_repository=verifications,
    )
    case.clock.now = datetime.now(UTC)
    expiry = case.grant.renewal.next_expiry(case.clock(), case.grant.expires_at)
    assert expiry is not None
    assert await case.repository.renew(
        case.grant.grant_id, case.grant.expires_at, expiry, now=case.clock()
    )
    # Let the old lease actually expire at Mongo too; only the snapshot CAS can
    # now distinguish it from the valid renewed lease.
    await asyncio.sleep(max(0, (case.grant.expires_at - datetime.now(UTC)).total_seconds()) + 0.02)
    assert not await case.repository.expire(
        case.grant.grant_id, case.grant.expires_at, now=datetime.now(UTC)
    )
    assert not await case.repository.expire(
        case.grant.grant_id, expiry, now=expiry + timedelta(seconds=1)
    )
    assert not (await case.repository.get(case.grant.grant_id)).grant.revoked
    expired = await RenewalCase.create(
        purpose,
        clock=VerificationClock(now=datetime.now(UTC) - timedelta(seconds=61)),
        review_repository=reviews,
        verification_repository=verifications,
        renewable=False,
    )
    expired.clock.now = datetime.now(UTC)
    await expired.service.reconcile()
    assert (await expired.repository.get(expired.grant.grant_id)).grant.revoked
