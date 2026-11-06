"""Purpose services recover one authorized issuance and retire its private material."""

import asyncio
from unittest.mock import AsyncMock

import pytest
from mas.application.access.executions import ExecutionAccessUnavailable
from mas.application.access.issuance import (
    CredentialIssuanceClosed,
    CredentialIssuanceConflict,
    CredentialMaterialRetirement,
    CredentialMaterialUnavailable,
)
from mas.core.identity import Identity
from support.credential_material import MemoryCredentialMaterial
from support.credential_renewals import RenewalCase


@pytest.fixture(params=["review", "verification"])
async def issuance_case(request):
    store = MemoryCredentialMaterial()
    case = await RenewalCase.create(request.param, material_store=store, key="initial")
    return case, store


@pytest.fixture
def material_retirement(issuance_case):
    case, store = issuance_case
    return CredentialMaterialRetirement(
        store, {case.service.purpose: case.service}, case.authority, clock=case.clock
    )


async def test_concurrent_identical_retries_recover_one_grant_and_original_material(issuance_case):
    case, store = issuance_case
    results = await asyncio.gather(*(case.reissue("initial") for _ in range(20)))
    for grant, secret in results:
        assert grant == case.grant
        assert secret.get_secret_value() == case.credential.get_secret_value()
    assert len(store.reservations) == len(store.credentials) == len(case.repository.records) == 1
    assert case.credential.get_secret_value() not in repr(store.reservations)


@pytest.mark.parametrize("change", ["root", "ttl", "horizon", "actions"])
async def test_an_issuance_key_cannot_change_its_admitted_request(issuance_case, change):
    case, store = issuance_case
    request = case.request
    if change == "root":
        request = request.model_copy(
            update={"scope": request.scope.model_copy(update={"root_execution_id": "different"})}
        )
    elif change == "actions":
        request = request.model_copy(
            update={
                "scope": request.scope.model_copy(
                    update={"actions": frozenset(sorted(request.scope.actions)[1:])}
                )
            }
        )
    elif change == "ttl":
        request = request.model_copy(update={"ttl_seconds": 61})
    else:
        request = request.model_copy(update={"renewable_for_seconds": 181})
    with pytest.raises(CredentialIssuanceConflict):
        await case.reissue("initial", request=request)
    assert len(store.reservations) == len(case.repository.records) == 1


@pytest.mark.parametrize("purpose", ["review", "verification"])
async def test_team_retry_requires_the_same_authenticated_human_approval(purpose):
    store = MemoryCredentialMaterial()
    case = await RenewalCase.create(
        purpose,
        material_store=store,
        key="initial",
        owner=Identity.team("team"),
        issued_by=Identity.user("issuer"),
    )
    with pytest.raises(CredentialIssuanceConflict):
        await case.reissue("initial", issued_by=Identity.user("other-human"))
    assert len(store.reservations) == len(case.repository.records) == 1


@pytest.mark.parametrize("committed", [False, True])
async def test_uncertain_registration_recovers_the_reserved_grant_without_reissuance(
    issuance_case, committed
):
    case, store = issuance_case
    original = case.repository.ensure

    async def lost_reply(access):
        if committed:
            await original(access)
        raise CredentialMaterialUnavailable()

    case.repository.ensure = lost_reply
    with pytest.raises(CredentialMaterialUnavailable):
        await case.reissue("uncertain")
    reserved = next(
        row for row in store.reservations.values() if row.grant_id != case.grant.grant_id
    )
    secret = store.credentials[reserved.binding_id]
    case.repository.ensure = original
    grant, recovered = await case.reissue("uncertain")
    assert grant.grant_id == reserved.grant_id
    assert recovered.get_secret_value() == secret.get_secret_value()
    assert len(store.reservations) == len(case.repository.records) == 2


async def test_retry_returns_current_renewal_without_resetting_issuance(issuance_case):
    case, _ = issuance_case
    case.clock.advance(41)
    await case.service.reconcile()
    grant, secret = await case.reissue("initial")
    assert grant.issued_at == case.grant.issued_at and grant.scope == case.grant.scope
    assert grant.expires_at > case.grant.expires_at
    assert secret.get_secret_value() == case.credential.get_secret_value()


@pytest.mark.parametrize("reason", ["revoked", "expired"])
async def test_closed_material_cannot_be_rejuvenated_and_audit_survives(
    issuance_case, material_retirement, reason
):
    case, store = issuance_case
    original = dict(store.reservations)
    if reason == "revoked":
        await case.service.revoke(case.grant.grant_id, case.grant.owner)
    else:
        case.clock.advance(181)
    with pytest.raises(CredentialIssuanceClosed):
        await case.reissue("initial")
    await material_retirement.reconcile()
    assert not store.credentials and store.reservations == original
    with pytest.raises(CredentialIssuanceClosed):
        await case.reissue("initial")


async def test_root_closure_between_reservation_and_registration_denies_the_reply(issuance_case):
    case, _ = issuance_case
    case.authority.closed = AsyncMock(side_effect=[False, True])
    with pytest.raises(CredentialIssuanceClosed):
        await case.reissue("initial")
    assert (await case.repository.get(case.grant.grant_id)).grant.revoked


@pytest.mark.parametrize("purpose", ["review", "verification"])
@pytest.mark.parametrize("observation", ["closed", "unavailable"])
async def test_direct_issuance_revokes_grant_if_root_cannot_be_confirmed(purpose, observation):
    case = await RenewalCase.create(purpose)
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


async def test_recoverable_issuance_remains_retryable_when_final_root_check_is_unavailable(
    issuance_case,
):
    case, _ = issuance_case
    case.authority.closed = AsyncMock(side_effect=[False, ExecutionAccessUnavailable()])
    with pytest.raises(ExecutionAccessUnavailable):
        await case.reissue("initial")
    assert not (await case.repository.get(case.grant.grant_id)).grant.revoked
    case.authority.closed = AsyncMock(return_value=False)
    grant, credential = await case.reissue("initial")
    assert grant == case.grant
    assert credential.get_secret_value() == case.credential.get_secret_value()


async def test_unknown_authority_preserves_material_but_known_closure_retires_it(
    issuance_case, material_retirement
):
    case, store = issuance_case
    case.authority.closed = AsyncMock(side_effect=ExecutionAccessUnavailable())
    await material_retirement.reconcile()
    assert store.credentials
    case.authority.closed = AsyncMock(return_value=True)
    await material_retirement.reconcile()
    assert not store.credentials
    assert (await case.repository.get(case.grant.grant_id)).grant.revoked


@pytest.mark.parametrize("purpose", ["review", "verification"])
async def test_keyed_issuance_without_configured_private_storage_fails_closed(purpose):
    case = await RenewalCase.create(purpose)
    with pytest.raises(CredentialMaterialUnavailable):
        await case.reissue("requires-private-storage")
    assert len(case.repository.records) == 1
