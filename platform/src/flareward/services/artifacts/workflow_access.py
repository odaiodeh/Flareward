"""Root-bound artifact capabilities use the shared managed credential lifecycle."""

from collections.abc import Callable, Sequence
from datetime import UTC, datetime, timedelta
from functools import partial
from typing import Protocol

from pydantic import ValidationError

from flareward.executions.domain.access import WorkflowAccess
from flareward.services.access.catalog import WorkflowAccessDescriptor
from flareward.services.access.credentials import OpaqueCredentials
from flareward.services.access.domain.leases import CredentialLease
from flareward.services.access.executions import ExecutionAccessUnavailable, ExecutionGrantAuthority
from flareward.services.access.issuance import (
    CredentialIssuance,
    CredentialIssuanceClosed,
    CredentialMaterialUnavailable,
    CredentialStatus,
    confirmed_grant,
)
from flareward.services.artifacts.access_models import (
    ArtifactAccessScope,
    ArtifactWorkflowGrant,
    ArtifactWorkflowRequest,
    StoredArtifactWorkflowAccess,
)
from flareward.services.artifacts.ports import ArtifactCredentialError, ArtifactMissing
from flareward.services.identity.domain import Identity


class ArtifactWorkflowRepository(Protocol):
    async def ensure(
        self, access: StoredArtifactWorkflowAccess
    ) -> StoredArtifactWorkflowAccess: ...
    async def get(
        self, grant_id: str, *, active_at: datetime | None = None
    ) -> StoredArtifactWorkflowAccess | None: ...
    async def revoke(self, grant_id: str) -> None: ...
    async def pending(
        self, *, after: str, limit: int
    ) -> Sequence[StoredArtifactWorkflowAccess]: ...
    async def expire(self, grant_id: str, expected_expiry: datetime, *, now: datetime) -> bool: ...
    async def renew(
        self, grant_id: str, expected_expiry: datetime, expires_at: datetime, *, now: datetime
    ) -> bool: ...


class ArtifactWorkflowAccessService:
    purpose = "artifact@1"

    def __init__(
        self,
        repository: ArtifactWorkflowRepository,
        *,
        execution_authority: ExecutionGrantAuthority,
        issuance: CredentialIssuance,
        max_bytes: int,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        if issuance.purpose != self.purpose or max_bytes < 1:
            raise ValueError("Artifact workflow access configuration is invalid")
        self._repository, self._executions, self._issuance = (
            repository,
            execution_authority,
            issuance,
        )
        self._max_bytes, self._now = max_bytes, clock or partial(datetime.now, UTC)
        self._credentials = OpaqueCredentials("flareward-artifact-workflow-v1")
        self._maintenance_cursor = ""

    def describe_workflow_access(self, owner: Identity) -> WorkflowAccessDescriptor:
        scope = ArtifactAccessScope.model_json_schema()
        scope["properties"]["max_bytes"]["maximum"] = min(
            self._max_bytes, scope["properties"]["max_bytes"]["maximum"]
        )
        # Require an explicit limit instead of advertising a changed runtime default.
        scope["required"].append("max_bytes")
        return WorkflowAccessDescriptor.from_models(
            self.purpose,
            "Artifact content",
            "Read or publish content in chosen owned namespaces or read exact artifact identities, "
            "within an explicit byte limit.",
            ArtifactWorkflowRequest,
            scope,
        )

    def _request(
        self, requirement: WorkflowAccess, root: str, owner: Identity, issued_by: Identity
    ) -> ArtifactWorkflowRequest:
        if requirement.purpose != self.purpose:
            raise ValueError("Workflow access purpose does not match artifact")
        try:
            request = ArtifactWorkflowRequest.model_validate(requirement.for_root(root))
        except ValidationError:
            raise ValueError("Workflow access violates the artifact scope contract") from None
        if (
            not owner.id
            or not issued_by.is_user
            or not issued_by.id
            or (owner.is_user and not owner.owns(issued_by))
        ):
            raise PermissionError("Artifact access requires authenticated human issuance")
        if request.scope.max_bytes > self._max_bytes:
            raise PermissionError("Artifact access exceeds its configured byte limit")
        return request

    def authorize_workflow_access(
        self, requirement: WorkflowAccess, root: str, owner: Identity, issued_by: Identity
    ) -> None:
        self._request(requirement, root, owner, issued_by)

    async def provision_workflow_access(
        self,
        requirement: WorkflowAccess,
        root: str,
        owner: Identity,
        issued_by: Identity,
        *,
        key: str,
    ) -> None:
        request = self._request(requirement, root, owner, issued_by)
        if await self._executions.closed(root, owner):
            raise CredentialIssuanceClosed()
        credential, now = self._credentials.issue(), self._now()
        grant = ArtifactWorkflowGrant(
            grant_id=credential.identifier,
            owner=owner.model_copy(deep=True),
            issued_by=issued_by.model_copy(deep=True),
            scope=request.scope.model_copy(deep=True),
            issued_at=now,
            expires_at=now + timedelta(seconds=request.ttl_seconds),
            renewal=CredentialLease(
                ttl_seconds=request.ttl_seconds,
                renewable_until=now + timedelta(seconds=request.renewable_for_seconds),
            )
            if request.renewable_for_seconds is not None
            else None,
        )
        grant, secret = await self._issuance.reserve(
            key,
            grant,
            credential.secret,
            root=root,
            request=request,
            ttl_seconds=request.ttl_seconds,
            renewable_for_seconds=request.renewable_for_seconds,
        )
        current = await self._repository.ensure(
            StoredArtifactWorkflowAccess(
                grant=grant, secret_sha256=self._credentials.digest(secret.get_secret_value())
            )
        )
        grant = confirmed_grant(
            grant, current.grant, secret, current.secret_sha256, self._credentials, self._now()
        )
        if await self._executions.closed(root, owner):
            await self._repository.revoke(grant.grant_id)
            raise CredentialIssuanceClosed()

    async def authenticate(self, credential: str) -> ArtifactWorkflowGrant:
        identifier = self._credentials.identify(credential)
        stored = (
            await self._repository.get(identifier, active_at=self._now()) if identifier else None
        )
        if (
            stored is None
            or stored.grant.revoked
            or stored.grant.scope.max_bytes > self._max_bytes
            or stored.grant.expires_at <= self._now()
            or not self._credentials.matches(credential, stored.secret_sha256)
        ):
            raise ArtifactCredentialError("Invalid artifact workflow credential")
        if not await self._executions.active(
            stored.grant.scope.root_execution_id, stored.grant.owner
        ):
            raise ArtifactCredentialError("Invalid artifact workflow credential")
        current = await self._repository.get(stored.grant.grant_id, active_at=self._now())
        if (
            current is None
            or current.grant.expires_at < stored.grant.expires_at
            or current.grant.expires_at
            > (
                stored.grant.renewal.renewable_until
                if stored.grant.renewal
                else stored.grant.expires_at
            )
            or current.grant.model_copy(update={"expires_at": stored.grant.expires_at})
            != stored.grant
            or not self._credentials.matches(credential, current.secret_sha256)
        ):
            raise ArtifactCredentialError("Invalid artifact workflow credential")
        return current.grant

    async def credential_status(self, grant_id: str, owner: Identity) -> CredentialStatus | None:
        stored = await self._repository.get(grant_id)
        if stored is None:
            return None
        if not stored.grant.owner.owns(owner):
            raise CredentialMaterialUnavailable()
        return CredentialStatus(stored.grant.scope.root_execution_id, stored.grant.revoked)

    async def revoke(self, grant_id: str, owner: Identity) -> None:
        stored = await self._repository.get(grant_id)
        if stored is None or not stored.grant.owner.owns(owner):
            raise ArtifactMissing("Artifact workflow access not found")
        await self._repository.revoke(grant_id)

    async def reconcile(self, limit: int = 100) -> None:
        if not 1 <= limit <= 100:
            raise ValueError("Credential maintenance page size must be between 1 and 100")
        now = self._now()
        records = await self._repository.pending(after=self._maintenance_cursor, limit=limit)
        if not records and self._maintenance_cursor:
            self._maintenance_cursor = ""
            records = await self._repository.pending(after="", limit=limit)
        for stored in records:
            grant = stored.grant
            self._maintenance_cursor = grant.grant_id
            if grant.revoked:
                continue
            if grant.scope.max_bytes > self._max_bytes:
                await self._repository.revoke(grant.grant_id)
                continue
            if grant.expires_at <= now:
                await self._repository.expire(grant.grant_id, grant.expires_at, now=now)
                continue
            try:
                expiry = grant.renewal.next_expiry(now, grant.expires_at) if grant.renewal else None
                if expiry is None:
                    if await self._executions.closed(grant.scope.root_execution_id, grant.owner):
                        await self._repository.revoke(grant.grant_id)
                    continue
                if await self._executions.active(grant.scope.root_execution_id, grant.owner):
                    current = self._now()
                    if grant.expires_at <= current:
                        await self._repository.expire(grant.grant_id, grant.expires_at, now=current)
                        continue
                    expiry = (
                        grant.renewal.next_expiry(current, grant.expires_at)
                        if grant.renewal
                        else None
                    )
                    if expiry is not None:
                        await self._repository.renew(
                            grant.grant_id, grant.expires_at, expiry, now=current
                        )
                elif await self._executions.closed(grant.scope.root_execution_id, grant.owner):
                    await self._repository.revoke(grant.grant_id)
            except ExecutionAccessUnavailable:
                continue
