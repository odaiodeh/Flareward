"""Shared managed-artifact scope and lifecycle contracts for owned storage ports."""

from dataclasses import dataclass
from datetime import UTC, datetime

import pytest
from mas.application.access.issuance import CredentialIssuance, CredentialIssuanceConflict
from mas.application.artifacts.access_models import StoredArtifactWorkflowAccess
from mas.application.artifacts.ports import ArtifactCredentialError
from mas.application.artifacts.workflow_access import (
    ArtifactWorkflowAccessService,
    ArtifactWorkflowRepository,
)
from mas.core.identity import Identity
from mas.domain.execution.access import WorkflowAccess

from support.credential_material import MemoryCredentialMaterial
from support.execution_access import ExecutionAuthority
from support.verification import VerificationClock


def artifact_requirement(**scope) -> WorkflowAccess:
    return WorkflowAccess(
        purpose="artifact@1",
        scope={"actions": ["read", "publish"], "namespaces": ["project"], **scope},
        ttl_seconds=60,
        renewable_for_seconds=180,
    )


class MemoryArtifactWorkflowRepository:
    def __init__(self) -> None:
        self.records: dict[str, StoredArtifactWorkflowAccess] = {}

    async def ensure(self, access: StoredArtifactWorkflowAccess) -> StoredArtifactWorkflowAccess:
        return self.records.setdefault(access.grant.grant_id, access)

    async def get(self, grant_id: str, *, active_at: datetime | None = None):
        stored = self.records.get(grant_id)
        if (
            stored
            and active_at is not None
            and (stored.grant.revoked or stored.grant.expires_at <= active_at)
        ):
            return None
        return stored

    async def revoke(self, grant_id: str) -> None:
        if stored := self.records.get(grant_id):
            self.records[grant_id] = stored.model_copy(
                update={"grant": stored.grant.model_copy(update={"revoked": True})}
            )

    async def pending(self, *, after: str, limit: int):
        return [
            row
            for key, row in sorted(self.records.items())
            if key > after and not row.grant.revoked
        ][:limit]

    async def expire(self, grant_id: str, expected_expiry: datetime, *, now: datetime) -> bool:
        stored = self.records.get(grant_id)
        if stored is None or stored.grant.expires_at != expected_expiry or expected_expiry > now:
            return False
        await self.revoke(grant_id)
        return True

    async def renew(
        self, grant_id: str, expected_expiry: datetime, expires_at: datetime, *, now: datetime
    ) -> bool:
        stored = self.records.get(grant_id)
        if (
            stored is None
            or stored.grant.revoked
            or stored.grant.renewal is None
            or (
                stored.grant.expires_at != expected_expiry
                or now >= expected_expiry
                or stored.grant.renewal.next_expiry(now, expected_expiry) != expires_at
            )
        ):
            return False
        self.records[grant_id] = stored.model_copy(
            update={"grant": stored.grant.model_copy(update={"expires_at": expires_at})}
        )
        return True


@dataclass
class ArtifactWorkflowCase:
    repository: ArtifactWorkflowRepository
    material: MemoryCredentialMaterial
    authority: ExecutionAuthority
    clock: VerificationClock
    owner: Identity
    service: ArtifactWorkflowAccessService

    @classmethod
    def create(cls, repository: ArtifactWorkflowRepository) -> ArtifactWorkflowCase:
        material = MemoryCredentialMaterial()
        authority = ExecutionAuthority()
        clock = VerificationClock(now=datetime.now(UTC))
        service = ArtifactWorkflowAccessService(
            repository,
            execution_authority=authority,
            issuance=CredentialIssuance("artifact@1", material),
            max_bytes=67_108_864,
            clock=clock,
        )
        return cls(repository, material, authority, clock, Identity.user("owner"), service)

    async def provision(self, *, root: str = "root", requirement: WorkflowAccess | None = None):
        await self.service.provision_workflow_access(
            requirement or artifact_requirement(), root, self.owner, self.owner, key="submission"
        )
        reservation = next(iter(self.material.reservations.values()))
        return reservation, self.material.credentials[reservation.binding_id].get_secret_value()


async def managed_artifact_lifecycle(case: ArtifactWorkflowCase) -> None:
    reservation, token = await case.provision()
    grant = await case.service.authenticate(token)
    assert grant.scope.root_execution_id == "root" and grant.owner == case.owner
    assert grant.scope.allows("publish", "project")
    assert not grant.scope.allows("read", "another-project")
    repeated, repeated_token = await case.provision()
    assert repeated == reservation and repeated_token == token
    for root, requirement in (
        ("other-root", artifact_requirement()),
        ("root", artifact_requirement(namespaces=["other-project"])),
    ):
        with pytest.raises(CredentialIssuanceConflict):
            await case.provision(root=root, requirement=requirement)
    case.clock.advance(41)
    await case.service.reconcile()
    renewed = await case.service.authenticate(token)
    assert renewed.expires_at > grant.expires_at and renewed.scope == grant.scope
    case.authority.live, case.authority.ended = False, True
    with pytest.raises(ArtifactCredentialError):
        await case.service.authenticate(token)
    await case.service.reconcile()
    assert (await case.repository.get(grant.grant_id)).grant.revoked
    case.authority.live, case.authority.ended = True, False
    with pytest.raises(ArtifactCredentialError):
        await case.service.authenticate(token)
