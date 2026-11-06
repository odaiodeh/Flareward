"""Actual private files preserve root isolation, cleanup recovery and stale-writer fencing."""

import asyncio
from datetime import UTC, datetime

import pytest
from mas.application.access.issuance import (
    CredentialIssuanceClosed,
    CredentialMaterial,
    CredentialMaterialRetirement,
    CredentialMaterialUnavailable,
)
from mas.core.identity import Identity
from mas.domain.execution.context import ExecutionContext
from mas_plugins.reviews.http import HTTPReviewGateway, ReviewTransportSettings
from mas_plugins.verification.http import HTTPVerificationGateway, VerificationTransportSettings
from outbound.run_engine.errors import application_errors
from outbound.workflow_credentials import FileWorkflowCredentials
from runengine.invocation.errors import InvocationInfrastructureError
from support.credential_material import MemoryCredentialMaterial
from support.credential_renewals import RenewalCase
from support.verification import VerificationClock


@pytest.fixture(params=["review", "verification"])
async def delivered_case(request, tmp_path):
    store = MemoryCredentialMaterial()
    delivery = FileWorkflowCredentials(tmp_path / "managed")
    case = await RenewalCase.create(
        request.param,
        clock=VerificationClock(now=datetime.now(UTC)),
        material_store=store,
        delivery=delivery,
        key="bound",
    )
    return case, store, delivery


async def test_concurrent_delivery_is_private_and_the_source_requires_exact_root(
    delivered_case, tmp_path
):
    case, store, delivery = delivered_case
    row = next(iter(store.reservations.values()))
    material = CredentialMaterial(row, case.credential)
    await asyncio.gather(*(delivery.deliver(material) for _ in range(8)))
    secret = await delivery.resolve(case.service.purpose, case.grant.owner, "root")
    assert secret.get_secret_value() == case.credential.get_secret_value()
    for path in (tmp_path / "managed").rglob("*"):
        assert path.stat().st_mode & 0o077 == 0
    with pytest.raises(CredentialMaterialUnavailable):
        await delivery.resolve(case.service.purpose, case.grant.owner, "foreign-root")
    with pytest.raises(CredentialMaterialUnavailable):
        await delivery.resolve(case.service.purpose, Identity.team(case.grant.owner.id), "root")
    with pytest.raises(CredentialMaterialUnavailable):
        await delivery.resolve("different@1", case.grant.owner, "root")


async def test_reconstructed_cleanup_recovers_a_lost_ack_and_fences_stale_delivery(
    delivered_case,
):
    case, store, delivery = delivered_case
    row = next(iter(store.reservations.values()))
    captured = CredentialMaterial(row, case.credential)
    await case.service.revoke(case.grant.grant_id, case.grant.owner)
    retire = delivery.retire

    async def lost_ack(reservation):
        await retire(reservation)
        raise CredentialMaterialUnavailable()

    delivery.retire = lost_ack
    reaper = CredentialMaterialRetirement(
        store,
        {case.service.purpose: case.service},
        case.authority,
        clock=case.clock,
        deliveries=(delivery,),
    )
    with pytest.raises(CredentialMaterialUnavailable):
        await reaper.reconcile()
    assert not store.credentials and row.binding_id in store.cleanup
    delivery.retire = retire
    replacement = CredentialMaterialRetirement(
        store,
        {case.service.purpose: case.service},
        case.authority,
        clock=case.clock,
        deliveries=(delivery,),
    )
    await replacement.reconcile()
    assert not store.cleanup
    with pytest.raises(CredentialIssuanceClosed):
        await delivery.deliver(captured)
    with pytest.raises(CredentialMaterialUnavailable):
        await delivery.resolve(case.service.purpose, case.grant.owner, "root")
    assert store.reservations[row.binding_id] == row


async def test_unknown_delivery_destination_preserves_cleanup_until_restored(
    delivered_case, tmp_path
):
    case, store, delivery = delivered_case
    changed = FileWorkflowCredentials(tmp_path / "different-destination")
    await case.service.revoke(case.grant.grant_id, case.grant.owner)
    reaper = CredentialMaterialRetirement(
        store,
        {case.service.purpose: case.service},
        case.authority,
        clock=case.clock,
        deliveries=(changed,),
    )
    await reaper.reconcile()
    assert store.cleanup and not (tmp_path / "different-destination").exists()
    restored = CredentialMaterialRetirement(
        store,
        {case.service.purpose: case.service},
        case.authority,
        clock=case.clock,
        deliveries=(delivery,),
    )
    await restored.reconcile()
    assert not store.cleanup


async def test_ambiguous_active_grants_are_refused_instead_of_widening_scope(delivered_case):
    case, store, delivery = delivered_case
    second, secret = await case.reissue("another-approval")
    with pytest.raises(CredentialMaterialUnavailable):
        await delivery.resolve(case.service.purpose, case.grant.owner, "root")
    await case.service.revoke(case.grant.grant_id, case.grant.owner)
    reaper = CredentialMaterialRetirement(
        store,
        {case.service.purpose: case.service},
        case.authority,
        clock=case.clock,
        deliveries=(delivery,),
    )
    await reaper.reconcile()
    resolved = await delivery.resolve(case.service.purpose, second.owner, "root")
    assert resolved.get_secret_value() == secret.get_secret_value()


async def test_unsafe_file_modes_and_symlink_replacement_fail_closed(delivered_case, tmp_path):
    case, _, delivery = delivered_case
    path = next((tmp_path / "managed").rglob("*.json"))
    path.chmod(0o644)
    with pytest.raises(CredentialMaterialUnavailable):
        await delivery.resolve(case.service.purpose, case.grant.owner, "root")
    path.chmod(0o600)
    path.unlink()
    unrelated = tmp_path / "operator-owned"
    unrelated.write_text("operator content")
    path.symlink_to(unrelated)
    with pytest.raises(CredentialMaterialUnavailable):
        await delivery.resolve(case.service.purpose, case.grant.owner, "root")
    assert unrelated.read_text() == "operator content"


@pytest.mark.parametrize(
    ("gateway_class", "settings_class"),
    [
        (HTTPReviewGateway, ReviewTransportSettings),
        (HTTPVerificationGateway, VerificationTransportSettings),
    ],
)
async def test_unavailable_managed_source_is_a_private_retryable_receiver_failure(
    tmp_path, gateway_class, settings_class
):
    gateway = gateway_class(
        settings_class(endpoint="https://example.invalid"),
        ExecutionContext(
            identity=Identity.user("owner"), execution_id="root", root_execution_id="root"
        ),
        source=FileWorkflowCredentials(tmp_path / "unavailable-private-source"),
    )
    try:
        with pytest.raises(InvocationInfrastructureError) as error:
            await application_errors(gateway.prepare_element)()
        assert error.value.retryable and str(tmp_path) not in str(error.value)
    finally:
        await gateway.aclose()
