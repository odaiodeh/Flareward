"""Real encrypted reservations and purpose repositories recover concurrent issuance."""

import asyncio
import json
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock

import pytest
from cryptography.fernet import Fernet
from support.credential_renewals import RenewalCase
from support.verification import VerificationClock

from lumora.services.access.adapters.mongo.credential_material import MongoCredentialMaterial
from lumora.services.access.adapters.workflow_credentials import FileWorkflowCredentials
from lumora.services.access.executions import ExecutionAccessUnavailable
from lumora.services.access.issuance import (
    CredentialIssuanceClosed,
    CredentialMaterial,
    CredentialMaterialRetirement,
    CredentialMaterialUnavailable,
)
from lumora.services.auth.adapters.crypto import FieldCipher
from lumora.services.reviews.adapters.mongo.reviews import MongoReviewAccessRepository
from lumora.services.reviews.ports import ReviewCredentialError
from lumora.services.verification.adapters.mongo.verification_access import (
    MongoVerificationAccessRepository,
)
from lumora.services.verification.ports import VerificationCredentialError


@pytest.fixture(params=["review", "verification"])
async def mongo_issuance_case(mongo_database, request):
    cipher = FieldCipher(Fernet.generate_key().decode())
    store = MongoCredentialMaterial(mongo_database, cipher)
    reviews = MongoReviewAccessRepository(mongo_database)
    verifications = MongoVerificationAccessRepository(mongo_database)
    await store.initialize()
    await reviews.initialize()
    await verifications.initialize()
    case = await RenewalCase.create(
        request.param,
        clock=VerificationClock(now=datetime.now(UTC)),
        material_store=store,
        key="initial",
        review_repository=reviews,
        verification_repository=verifications,
    )
    return case, store, cipher


async def test_concurrent_issuance_stores_one_encrypted_material_and_one_grant(
    mongo_database, mongo_issuance_case
):
    case, store, cipher = mongo_issuance_case
    results = await asyncio.gather(*(case.reissue("initial") for _ in range(12)))
    for grant, credential in results:
        assert grant == case.grant
        assert credential.get_secret_value() == case.credential.get_secret_value()
    assert await mongo_database.workflow_credential_material.count_documents({}) == 1
    document = await mongo_database.workflow_credential_material.find_one({})
    assert case.credential.get_secret_value() not in json.dumps(document)
    assert cipher.decrypt(document["credential"]) == case.credential.get_secret_value()
    assert len(await case.repository.pending(after="", limit=100)) == 1
    # Grant renewal remains authoritative; registration retries never replace it.
    case.clock.advance(41)
    await case.service.reconcile()
    grant, _ = await case.reissue("initial")
    assert grant.expires_at > case.grant.expires_at and grant.issued_at == case.grant.issued_at
    await case.service.revoke(grant.grant_id, grant.owner)
    with pytest.raises(CredentialIssuanceClosed):
        await case.reissue("initial")
    reaper = CredentialMaterialRetirement(
        store, {case.service.purpose: case.service}, case.authority, clock=case.clock
    )
    await reaper.reconcile()
    retired = await mongo_database.workflow_credential_material.find_one({})
    assert retired["retired"] and "credential" not in retired
    assert retired["data"] == document["data"]
    with pytest.raises(CredentialIssuanceClosed):
        await case.reissue("initial")


async def test_fast_application_clock_cannot_expire_live_private_material(
    mongo_database, mongo_issuance_case
):
    case, store, _ = mongo_issuance_case
    reservation = (await store.pending(after="", limit=100))[0]
    assert not await store.expire(
        reservation, now=reservation.maximum_expiry + timedelta(seconds=1)
    )
    assert "credential" in await mongo_database.workflow_credential_material.find_one({})


async def test_slow_application_clock_cannot_authenticate_database_expired_grant(
    mongo_database, mongo_issuance_case
):
    original, _, _ = mongo_issuance_case
    review = original.service.purpose == "review@1"
    expired = await RenewalCase.create(
        "review" if review else "verification",
        clock=VerificationClock(now=datetime.now(UTC) - timedelta(seconds=181)),
        review_repository=original.repository if review else None,
        verification_repository=None if review else original.repository,
    )
    with pytest.raises(ReviewCredentialError if review else VerificationCredentialError):
        await expired.service.authenticate(expired.credential.get_secret_value())
    # The ordinary audit read remains available after expiry.
    assert await original.repository.get(expired.grant.grant_id) is not None


@pytest.mark.parametrize("change", ["revoke", "expire", "renew"])
async def test_authentication_rechecks_after_root_observation(mongo_issuance_case, change):
    case, _, _ = mongo_issuance_case
    review = case.service.purpose == "review@1"

    async def active(root, owner):
        if change == "revoke":
            await case.repository.revoke(case.grant.grant_id)
        elif change == "expire":
            case.clock.advance(61)
        else:
            case.clock.advance(41)
            assert await case.repository.renew(
                case.grant.grant_id,
                case.grant.expires_at,
                case.clock() + timedelta(seconds=60),
                now=case.clock(),
            )
        return True

    case.authority.active = AsyncMock(side_effect=active)
    if change == "renew":
        grant = await case.service.authenticate(case.credential.get_secret_value())
        assert grant.expires_at > case.grant.expires_at
        return
    with pytest.raises(ReviewCredentialError if review else VerificationCredentialError):
        await case.service.authenticate(case.credential.get_secret_value())


@pytest.mark.parametrize("observation", ["closed", "unavailable"])
async def test_direct_issuance_retires_new_grant_after_failed_final_root_check(
    mongo_issuance_case, observation
):
    case, _, _ = mongo_issuance_case
    result = True if observation == "closed" else ExecutionAccessUnavailable()
    case.authority.closed = AsyncMock(side_effect=[False, result])
    original_create = case.repository.create
    created = []

    async def capture_create(access):
        await original_create(access)
        created.append(access.grant.grant_id)

    case.repository.create = capture_create
    error = CredentialIssuanceClosed if observation == "closed" else ExecutionAccessUnavailable
    with pytest.raises(error):
        await case.reissue(None)
    assert len(created) == 1
    assert (await case.repository.get(created[0])).grant.revoked


async def test_plaintext_passthrough_and_invalid_ciphertext_are_refused(
    mongo_database, mongo_issuance_case
):
    case, _, _ = mongo_issuance_case
    await mongo_database.workflow_credential_material.update_one(
        {}, {"$set": {"credential": case.credential.get_secret_value()}}
    )
    # The shared legacy-compatible field cipher accepts plaintext; this new vault
    # deliberately requires actual protected material instead of passing it through.
    with pytest.raises(CredentialMaterialUnavailable):
        await case.reissue("initial")


async def test_maximum_expiry_retires_ciphertext_without_native_authority(
    mongo_database, mongo_issuance_case
):
    case, store, _ = mongo_issuance_case
    review = case.service.purpose == "review@1"
    expired = await RenewalCase.create(
        "review" if review else "verification",
        clock=VerificationClock(now=datetime.now(UTC) - timedelta(seconds=181)),
        material_store=store,
        key="expired",
        review_repository=case.repository if review else None,
        verification_repository=None if review else case.repository,
    )
    before = await mongo_database.workflow_credential_material.find_one(
        {"data": {"$regex": expired.grant.grant_id}}
    )
    case.authority.closed = AsyncMock(side_effect=ExecutionAccessUnavailable())
    reaper = CredentialMaterialRetirement(
        store,
        {case.service.purpose: case.service},
        case.authority,
        clock=VerificationClock(now=datetime.now(UTC)),
    )
    await reaper.reconcile()
    retired = await mongo_database.workflow_credential_material.find_one({"_id": before["_id"]})
    assert retired["retired"] and "credential" not in retired
    assert retired["data"] == before["data"]
    assert (
        await mongo_database.workflow_credential_material.count_documents({"retired": False}) == 1
    )


async def test_persisted_cleanup_outbox_recovers_after_controller_reconstruction(
    mongo_database, mongo_issuance_case, tmp_path
):
    original, store, cipher = mongo_issuance_case
    directory = tmp_path / "managed"
    delivery = FileWorkflowCredentials(directory)
    review = original.service.purpose == "review@1"
    case = await RenewalCase.create(
        "review" if review else "verification",
        clock=VerificationClock(now=datetime.now(UTC)),
        material_store=store,
        delivery=delivery,
        key="managed",
        review_repository=original.repository if review else None,
        verification_repository=None if review else original.repository,
    )
    reservation = next(
        row
        for row in await store.pending(after="", limit=100)
        if row.grant_id == case.grant.grant_id
    )
    captured = CredentialMaterial(reservation, case.credential)
    before = await mongo_database.workflow_credential_material.find_one(
        {"_id": reservation.binding_id}
    )
    await case.service.revoke(case.grant.grant_id, case.grant.owner)
    delivery.retire = AsyncMock(side_effect=CredentialMaterialUnavailable())
    reaper = CredentialMaterialRetirement(
        store,
        {case.service.purpose: case.service},
        case.authority,
        clock=case.clock,
        deliveries=(delivery,),
    )
    with pytest.raises(CredentialMaterialUnavailable):
        await reaper.reconcile()
    retired = await mongo_database.workflow_credential_material.find_one(
        {"_id": reservation.binding_id}
    )
    assert retired["retired"] and retired["cleanup_pending"] and "credential" not in retired
    assert list(directory.rglob("*.json"))
    # Residual bytes after a failed collection do not retain live grant authority.
    stored_grant = await case.repository.get(case.grant.grant_id)
    assert stored_grant.grant.revoked
    replacement_store = MongoCredentialMaterial(mongo_database, cipher)
    await replacement_store.initialize()
    replacement_delivery = FileWorkflowCredentials(directory)
    replacement = CredentialMaterialRetirement(
        replacement_store,
        {case.service.purpose: case.service},
        case.authority,
        clock=case.clock,
        deliveries=(replacement_delivery,),
    )
    await replacement.reconcile()
    cleaned = await mongo_database.workflow_credential_material.find_one(
        {"_id": reservation.binding_id}
    )
    assert cleaned["retired"] and not cleaned["cleanup_pending"]
    assert "credential" not in cleaned and cleaned["data"] == before["data"]
    assert not list(directory.rglob("*.json"))
    with pytest.raises(CredentialIssuanceClosed):
        await replacement_delivery.deliver(captured)
    with pytest.raises(CredentialMaterialUnavailable):
        await replacement_delivery.resolve(case.service.purpose, case.grant.owner, "root")
