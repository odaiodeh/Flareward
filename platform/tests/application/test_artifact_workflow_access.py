"""Root-scoped artifact authority follows the common managed credential lifecycle."""

import pytest
from support.artifact_workflow import (
    ArtifactWorkflowCase,
    MemoryArtifactWorkflowRepository,
    artifact_requirement,
    managed_artifact_lifecycle,
)

from flareward.services.access.issuance import (
    CredentialIssuance,
    CredentialIssuanceClosed,
    CredentialMaterialRetirement,
)
from flareward.services.artifacts.ports import ArtifactCredentialError, ArtifactStorageError
from flareward.services.identity.domain import Identity


async def test_managed_artifact_lifecycle():
    await managed_artifact_lifecycle(
        ArtifactWorkflowCase.create(MemoryArtifactWorkflowRepository())
    )


@pytest.mark.parametrize("reason", ["owner", "human", "limit"])
async def test_unauthorized_artifact_requests_create_no_material(reason):
    case = ArtifactWorkflowCase.create(MemoryArtifactWorkflowRepository())
    with pytest.raises(PermissionError):
        await case.service.provision_workflow_access(
            artifact_requirement(max_bytes=1_073_741_824)
            if reason == "limit"
            else artifact_requirement(),
            "root",
            case.owner,
            Identity.user("another")
            if reason == "owner"
            else Identity.team("team")
            if reason == "human"
            else case.owner,
            key="submission",
        )
    assert not case.material.reservations


async def test_revocation_during_root_observation_is_rechecked(monkeypatch):
    case = ArtifactWorkflowCase.create(MemoryArtifactWorkflowRepository())
    reservation, token = await case.provision()

    async def active(root, owner):
        await case.repository.revoke(reservation.grant_id)
        return True

    monkeypatch.setattr(case.authority, "active", active)
    with pytest.raises(ArtifactCredentialError):
        await case.service.authenticate(token)


async def test_closed_root_cannot_provision_or_revive_retired_material():
    case = ArtifactWorkflowCase.create(MemoryArtifactWorkflowRepository())
    reservation, token = await case.provision()
    case.authority.live, case.authority.ended = False, True
    await CredentialMaterialRetirement(
        case.material, {case.service.purpose: case.service}, case.authority
    ).reconcile()
    assert reservation.binding_id in case.material.retired and not case.material.credentials
    with pytest.raises(CredentialIssuanceClosed):
        await case.provision()
    with pytest.raises(ArtifactCredentialError):
        await case.service.authenticate(token)


async def test_reduced_byte_policy_revokes_existing_grants():
    case = ArtifactWorkflowCase.create(MemoryArtifactWorkflowRepository())
    reservation, token = await case.provision()
    service = type(case.service)(
        case.repository,
        execution_authority=case.authority,
        issuance=CredentialIssuance("artifact@1", case.material),
        max_bytes=1024,
        clock=case.clock,
    )
    with pytest.raises(ArtifactCredentialError):
        await service.authenticate(token)
    await service.reconcile()
    assert (await case.repository.get(reservation.grant_id)).grant.revoked


async def test_expired_artifact_grant_cannot_be_renewed_or_reprovisioned():
    case = ArtifactWorkflowCase.create(MemoryArtifactWorkflowRepository())
    reservation, token = await case.provision()
    case.clock.advance(61)
    with pytest.raises(ArtifactCredentialError):
        await case.service.authenticate(token)
    await case.service.reconcile()
    assert (await case.repository.get(reservation.grant_id)).grant.revoked
    with pytest.raises(CredentialIssuanceClosed):
        await case.provision()


async def test_uncertain_registration_recovers_original_grant(monkeypatch):
    repository = MemoryArtifactWorkflowRepository()
    case = ArtifactWorkflowCase.create(repository)
    ensure = repository.ensure

    async def uncertain(access):
        await ensure(access)
        raise ArtifactStorageError("Artifact workflow access storage is unavailable")

    monkeypatch.setattr(repository, "ensure", uncertain)
    with pytest.raises(ArtifactStorageError):
        await case.provision()
    original = next(iter(case.material.reservations.values()))
    monkeypatch.setattr(repository, "ensure", ensure)
    recovered, token = await case.provision()
    assert recovered == original and len(repository.records) == 1
    assert (await case.service.authenticate(token)).grant_id == original.grant_id
