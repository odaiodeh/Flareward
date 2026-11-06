"""Renewal preserves authority, fixed lifetime and revocation across purpose services."""

from unittest.mock import AsyncMock

import pytest
from mas.application.access.executions import ExecutionAccessUnavailable
from mas.application.reviews.access import ReviewAccessService
from mas.application.reviews.ports import ReviewCredentialError
from mas.application.verification.access import VerificationAccessService
from mas.application.verification.access_models import (
    VerificationAccessRequest,
    VerificationAccessScope,
    VerificationAction,
)
from mas.application.verification.ports import VerificationCredentialError
from support.credential_renewals import RenewalCase
from support.reviews import review_policy
from support.verification import verification_policy


@pytest.fixture(params=["review", "verification"])
async def credential_case(request):
    return await RenewalCase.create(request.param)


async def test_renewal_preserves_scope_secret_hash_and_issuer_and_stops_at_horizon(credential_case):
    case = credential_case
    original = await case.repository.get(case.grant.grant_id)
    await case.service.reconcile()
    assert await case.repository.get(case.grant.grant_id) == original
    for advance in (41, 40, 40):
        case.clock.advance(advance)
        await case.service.reconcile()
        stored = await case.repository.get(case.grant.grant_id)
        grant = stored.grant
        assert grant.expires_at > case.grant.expires_at
        assert grant.scope == case.grant.scope and grant.issued_at == case.grant.issued_at
        assert grant.issued_by == case.grant.issued_by
        assert stored.secret_sha256 == original.secret_sha256
        assert (await case.service.authenticate(case.credential.get_secret_value())) == grant
    assert grant.expires_at == grant.renewal.renewable_until
    case.clock.advance(60)
    await case.service.reconcile()
    assert (await case.repository.get(grant.grant_id)).grant.expires_at == grant.expires_at
    with pytest.raises((ReviewCredentialError, VerificationCredentialError)):
        await case.service.authenticate(case.credential.get_secret_value())


async def test_unknown_authority_does_not_extend_or_revoke_and_expiry_cannot_resurrect(
    credential_case,
):
    case = credential_case
    case.clock.advance(41)
    case.authority.active = AsyncMock(side_effect=ExecutionAccessUnavailable())
    await case.service.reconcile()
    stored = await case.repository.get(case.grant.grant_id)
    assert not stored.grant.revoked and stored.grant.expires_at == case.grant.expires_at
    case.clock.advance(20)
    case.authority.active = AsyncMock(return_value=True)
    await case.service.reconcile()
    assert (
        await case.repository.get(case.grant.grant_id)
    ).grant.expires_at == case.grant.expires_at


async def test_revocation_and_closed_root_stop_renewal(credential_case):
    case = credential_case
    case.clock.advance(41)
    case.authority.live = False
    case.authority.ended = True
    await case.service.reconcile()
    stored = await case.repository.get(case.grant.grant_id)
    assert stored.grant.revoked and stored.grant.expires_at == case.grant.expires_at
    case.authority.live = True
    await case.service.reconcile()
    assert (await case.repository.get(case.grant.grant_id)).grant.revoked


async def test_expiry_is_rechecked_after_an_authority_query(credential_case):
    case = credential_case
    case.clock.advance(41)

    async def slow_authority(root, owner):
        case.clock.advance(20)
        return True

    case.authority.active = slow_authority
    await case.service.reconcile()
    assert (
        await case.repository.get(case.grant.grant_id)
    ).grant.expires_at == case.grant.expires_at


@pytest.mark.parametrize("purpose", ["review", "verification"])
async def test_nonrenewable_grants_keep_their_fixed_expiry(purpose):
    case = await RenewalCase.create(purpose, renewable=False)
    case.clock.advance(41)
    await case.service.reconcile()
    assert (await case.repository.get(case.grant.grant_id)).grant == case.grant


async def test_pending_root_does_not_extend_but_can_renew_after_activation(credential_case):
    case = credential_case
    case.clock.advance(41)
    case.authority.live = False
    await case.service.reconcile()
    stored = await case.repository.get(case.grant.grant_id)
    assert not stored.grant.revoked and stored.grant.expires_at == case.grant.expires_at
    case.authority.live = True
    await case.service.reconcile()
    assert (await case.repository.get(case.grant.grant_id)).grant.expires_at > case.grant.expires_at


@pytest.mark.parametrize("allowed", [False, True])
async def test_restarted_maintainer_rechecks_policy_without_new_secret_material(
    credential_case, allowed
):
    case = credential_case
    case.clock.advance(41)
    original = await case.repository.get(case.grant.grant_id)
    policy = review_policy if isinstance(case.service, ReviewAccessService) else verification_policy
    replacement = type(case.service)(
        case.repository,
        {"release@1": policy(case.grant.owner)} if allowed else {},
        clock=case.clock,
        execution_authority=case.authority,
    )
    await replacement.reconcile()
    stored = await case.repository.get(case.grant.grant_id)
    assert stored.secret_sha256 == original.secret_sha256
    assert stored.grant.revoked == (not allowed)
    assert (stored.grant.expires_at > case.grant.expires_at) == allowed


async def test_bounded_pages_skip_unavailable_authority_and_revisit_it_after_wrap(credential_case):
    case = credential_case
    review = isinstance(case.service, ReviewAccessService)
    cases = [case]
    for _ in range(2):
        cases.append(
            await RenewalCase.create(
                "review" if review else "verification",
                clock=case.clock,
                review_repository=case.repository if review else None,
                verification_repository=None if review else case.repository,
            )
        )
    cases.sort(key=lambda item: item.grant.grant_id)
    case.clock.advance(41)
    case.authority.active = AsyncMock(
        side_effect=[ExecutionAccessUnavailable(), True, True, True]
    )
    for _ in range(3):
        await case.service.reconcile(limit=1)
    for index, item in enumerate(cases):
        stored = await case.repository.get(item.grant.grant_id)
        assert (stored.grant.expires_at > item.grant.expires_at) == (index > 0)
    await case.service.reconcile(limit=1)
    assert (
        await case.repository.get(cases[0].grant.grant_id)
    ).grant.expires_at > cases[0].grant.expires_at
    assert case.authority.active.await_count == 4


@pytest.mark.parametrize("purpose", ["review", "verification"])
@pytest.mark.parametrize("renewable", [False, True])
async def test_closed_roots_retire_every_grant_before_renewal_is_due(purpose, renewable):
    case = await RenewalCase.create(purpose, renewable=renewable)
    case.authority.live = False
    case.authority.ended = True
    await case.service.reconcile()
    stored = await case.repository.get(case.grant.grant_id)
    assert stored.grant.revoked
    assert stored.grant.expires_at == case.grant.expires_at
    assert stored.grant.issued_by == case.grant.issued_by
    assert not await case.repository.pending(after="", limit=100)


@pytest.mark.parametrize("purpose", ["review", "verification"])
@pytest.mark.parametrize("renewable", [False, True])
async def test_withdrawn_policy_retires_fixed_and_renewable_grants(purpose, renewable):
    case = await RenewalCase.create(purpose, renewable=renewable)
    replacement = type(case.service)(
        case.repository, {}, execution_authority=case.authority, clock=case.clock
    )
    await replacement.reconcile()
    assert (await case.repository.get(case.grant.grant_id)).grant.revoked


async def test_expiry_retirement_needs_no_native_authority_and_keeps_the_audit(credential_case):
    case = credential_case
    original = await case.repository.get(case.grant.grant_id)
    case.clock.advance(61)
    case.authority.active = AsyncMock(side_effect=ExecutionAccessUnavailable())
    case.authority.closed = AsyncMock(side_effect=ExecutionAccessUnavailable())
    await case.service.reconcile()
    stored = await case.repository.get(case.grant.grant_id)
    assert stored.grant.revoked and stored.secret_sha256 == original.secret_sha256
    assert stored.grant.model_copy(update={"revoked": False}) == original.grant
    case.authority.active.assert_not_awaited()
    case.authority.closed.assert_not_awaited()


async def test_unknown_authority_before_renewal_is_due_preserves_the_grant(credential_case):
    case = credential_case
    case.authority.closed = AsyncMock(side_effect=ExecutionAccessUnavailable())
    await case.service.reconcile()
    assert (await case.repository.get(case.grant.grant_id)).grant == case.grant


@pytest.mark.parametrize("renewable", [False, True])
async def test_read_cancel_verification_access_preserves_its_frozen_plan_scope(renewable):
    case = await RenewalCase.create("verification")
    assert isinstance(case.service, VerificationAccessService)
    issued = await case.service.issue(
        VerificationAccessRequest(
            scope=VerificationAccessScope(
                root_execution_id="root",
                policies=frozenset({"release@1"}),
                actions=frozenset({VerificationAction.READ, VerificationAction.CANCEL}),
            ),
            ttl_seconds=60,
            renewable_for_seconds=180 if renewable else None,
        ),
        case.grant.owner,
        case.grant.issued_by,
    )
    replacement = VerificationAccessService(
        case.repository, {}, execution_authority=case.authority, clock=case.clock
    )
    case.clock.advance(41)
    await replacement.reconcile()
    grant = await replacement.authenticate(issued.credential.get_secret_value())
    assert grant.scope == issued.grant.scope
    assert (grant.expires_at > issued.grant.expires_at) == renewable
    # Removing creation policy did not widen this grant or remove frozen-plan
    # authority, but neither read nor cancel may outlive the actual root.
    case.authority.live = False
    case.authority.ended = True
    await replacement.reconcile()
    assert (await case.repository.get(grant.grant_id)).grant.revoked
