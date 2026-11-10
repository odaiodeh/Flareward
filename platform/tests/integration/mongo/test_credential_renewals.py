"""Actual Mongo CAS preserves the fixed lease and wins no race against revocation."""

import asyncio
from datetime import UTC, datetime, timedelta

import pytest
from support.credential_renewals import RenewalCase
from support.verification import VerificationClock

from lumora.services.reviews.adapters.mongo.reviews import MongoReviewAccessRepository
from lumora.services.verification.adapters.mongo.verification_access import (
    MongoVerificationAccessRepository,
)


@pytest.mark.parametrize("purpose", ["review", "verification"])
async def test_atomic_renewal_preserves_hash_and_never_resurrects_revoked_or_expired_grants(
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
    )
    original = await case.repository.get(case.grant.grant_id)
    case.clock.advance(41)
    pending = await case.repository.pending(after="", limit=100)
    assert [record.grant.grant_id for record in pending] == [case.grant.grant_id]
    expiry = case.grant.renewal.next_expiry(case.clock(), case.grant.expires_at)
    results = await asyncio.gather(
        *(
            case.repository.renew(
                case.grant.grant_id, case.grant.expires_at, expiry, now=case.clock()
            )
            for _ in range(10)
        )
    )
    assert results.count(True) == 1
    stored = await case.repository.get(case.grant.grant_id)
    assert stored.secret_sha256 == original.secret_sha256
    assert stored.grant.scope == original.grant.scope and stored.grant.expires_at == expiry
    assert not await case.repository.renew(
        case.grant.grant_id, expiry, expiry + timedelta(days=31), now=case.clock()
    )
    case.clock.advance(40)
    following = stored.grant.renewal.next_expiry(case.clock(), expiry)
    await asyncio.gather(
        case.repository.renew(case.grant.grant_id, expiry, following, now=case.clock()),
        case.repository.revoke(case.grant.grant_id),
    )
    assert (await case.repository.get(case.grant.grant_id)).grant.revoked
    assert not await case.repository.renew(case.grant.grant_id, expiry, following, now=case.clock())
    # The database clock is an additional fence even if a caller's clock is stale.
    expired = await RenewalCase.create(
        purpose,
        clock=VerificationClock(now=datetime.now(UTC) - timedelta(seconds=61)),
        review_repository=reviews,
        verification_repository=verifications,
    )
    expired.clock.advance(41)
    assert not await expired.repository.renew(
        expired.grant.grant_id,
        expired.grant.expires_at,
        expired.grant.renewal.next_expiry(expired.clock(), expired.grant.expires_at),
        now=expired.clock(),
    )
