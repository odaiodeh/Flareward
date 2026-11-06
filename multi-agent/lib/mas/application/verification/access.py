"""Issue and revoke root/policy-bound workflow access, independently of verifier authority."""

from collections.abc import Callable, Mapping
from datetime import UTC, datetime, timedelta
from functools import partial

from pydantic import ValidationError

from mas.application.access.catalog import WorkflowAccessDescriptor
from mas.application.access.credentials import OpaqueCredentials
from mas.application.access.executions import ExecutionAccessUnavailable, ExecutionGrantAuthority
from mas.application.access.issuance import (
    CredentialIssuance,
    CredentialIssuanceClosed,
    CredentialMaterialUnavailable,
    CredentialStatus,
    confirmed_grant,
)
from mas.application.verification.access_models import (
    IssuedVerificationAccess,
    StoredVerificationAccess,
    VerificationAccessGrant,
    VerificationAccessRequest,
    VerificationAccessScope,
    VerificationAction,
    VerificationPermissions,
)
from mas.application.verification.models import VerificationPolicy
from mas.application.verification.ports import (
    VerificationAccessRepository,
    VerificationCredentialError,
    VerificationMissing,
)
from mas.core.identity import Identity
from mas.domain.credential_leases import CredentialLease
from mas.domain.execution.access import WorkflowAccess


class VerificationAccessService:
    purpose = "verification@1"

    def __init__(
        self,
        repository: VerificationAccessRepository,
        policies: Mapping[str, VerificationPolicy],
        *,
        execution_authority: ExecutionGrantAuthority,
        issuance: CredentialIssuance | None = None,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._repository = repository
        if issuance is not None and issuance.purpose != self.purpose:
            raise ValueError("Verification issuance purpose does not match")
        self._issuance = issuance
        self._executions = execution_authority
        self._policies = {key: value.model_copy(deep=True) for key, value in policies.items()}
        self._now = clock or partial(datetime.now, UTC)
        self._credentials = OpaqueCredentials("unifai-verification-v1")
        self._maintenance_cursor = ""

    def describe_workflow_access(self, owner: Identity) -> WorkflowAccessDescriptor | None:
        policies = sorted(
            name
            for name, policy in self._policies.items()
            if any(allowed.owns(owner) for allowed in policy.owners)
        )
        if not policies:
            return None
        scope = VerificationPermissions.model_json_schema()
        scope["properties"]["policies"]["items"] = {"type": "string", "enum": policies}
        return WorkflowAccessDescriptor.from_models(
            self.purpose,
            "Verification plans and checks",
            "Manage plans and request trusted checks under selected policies. "
            "This does not grant verifier evidence submission.",
            VerificationAccessRequest,
            scope,
        )

    def _permitted(self, scope: VerificationAccessScope, owner: Identity) -> bool:
        return not scope.actions.intersection(
            {VerificationAction.CREATE, VerificationAction.RUN_CHECK}
        ) or all(
            name in self._policies
            and any(allowed.owns(owner) for allowed in self._policies[name].owners)
            for name in scope.policies
        )

    def _authorize(
        self, request: VerificationAccessRequest, owner: Identity, issued_by: Identity
    ) -> None:
        if not owner.id or not issued_by.is_user or not issued_by.id:
            raise PermissionError("Verification access requires authenticated human issuance")
        if owner.is_user and not owner.owns(issued_by):
            raise PermissionError("Verification access issuer does not match its owner")
        if not self._permitted(request.scope, owner):
            raise PermissionError("Verification policy is not permitted")

    def _workflow_request(
        self, requirement: WorkflowAccess, root: str
    ) -> VerificationAccessRequest:
        if requirement.purpose != self.purpose:
            raise ValueError("Workflow access purpose does not match verification")
        try:
            return VerificationAccessRequest.model_validate(requirement.for_root(root))
        except ValidationError:
            raise ValueError("Workflow access violates the verification scope contract") from None

    def authorize_workflow_access(
        self, requirement: WorkflowAccess, root: str, owner: Identity, issued_by: Identity
    ) -> None:
        self._authorize(self._workflow_request(requirement, root), owner, issued_by)

    async def provision_workflow_access(
        self,
        requirement: WorkflowAccess,
        root: str,
        owner: Identity,
        issued_by: Identity,
        *,
        key: str,
    ) -> None:
        await self.issue(self._workflow_request(requirement, root), owner, issued_by, key=key)

    async def issue(
        self,
        request: VerificationAccessRequest,
        owner: Identity,
        issued_by: Identity,
        *,
        key: str | None = None,
    ) -> IssuedVerificationAccess:
        self._authorize(request, owner, issued_by)
        if await self._executions.closed(request.scope.root_execution_id, owner):
            raise PermissionError("Verification access root is closed or unavailable")
        credential, now = self._credentials.issue(), self._now()
        grant = VerificationAccessGrant(
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
        secret = credential.secret
        if key is not None:
            if self._issuance is None:
                raise CredentialMaterialUnavailable()
            grant, secret = await self._issuance.reserve(
                key,
                grant,
                secret,
                root=request.scope.root_execution_id,
                request=request,
                ttl_seconds=request.ttl_seconds,
                renewable_for_seconds=request.renewable_for_seconds,
            )
        stored = StoredVerificationAccess(
            grant=grant, secret_sha256=self._credentials.digest(secret.get_secret_value())
        )
        if key is None:
            await self._repository.create(stored)
        else:
            current = await self._repository.ensure(stored)
            grant = confirmed_grant(
                grant, current.grant, secret, current.secret_sha256, self._credentials, self._now()
            )
        try:
            closed = await self._executions.closed(grant.scope.root_execution_id, owner)
        except ExecutionAccessUnavailable:
            if key is None:
                await self._repository.revoke(grant.grant_id)
            raise
        if closed:
            await self._repository.revoke(grant.grant_id)
            raise CredentialIssuanceClosed()
        return IssuedVerificationAccess(grant, secret)

    async def credential_status(self, grant_id: str, owner: Identity) -> CredentialStatus | None:
        stored = await self._repository.get(grant_id)
        if stored is None:
            return None
        if not stored.grant.owner.owns(owner):
            raise CredentialMaterialUnavailable()
        return CredentialStatus(stored.grant.scope.root_execution_id, stored.grant.revoked)

    async def authenticate(self, credential: str) -> VerificationAccessGrant:
        identifier = self._credentials.identify(credential)
        stored = (
            await self._repository.get(identifier, active_at=self._now())
            if identifier is not None
            else None
        )
        if (
            stored is None
            or stored.grant.revoked
            or stored.grant.expires_at <= self._now()
            or not self._credentials.matches(credential, stored.secret_sha256)
        ):
            raise VerificationCredentialError("Invalid verification credential")
        if not await self._executions.active(
            stored.grant.scope.root_execution_id, stored.grant.owner
        ):
            raise VerificationCredentialError("Invalid verification credential")
        current = await self._repository.get(stored.grant.grant_id, active_at=self._now())
        if (
            current is None
            or current.grant.expires_at < stored.grant.expires_at
            or current.grant.expires_at
            > (
                stored.grant.renewal.renewable_until
                if stored.grant.renewal is not None
                else stored.grant.expires_at
            )
            or current.grant.model_copy(update={"expires_at": stored.grant.expires_at})
            != stored.grant
            or not self._credentials.matches(credential, current.secret_sha256)
        ):
            raise VerificationCredentialError("Invalid verification credential")
        return current.grant

    async def list(
        self, owner: Identity, *, after: str = "", limit: int = 100
    ) -> list[VerificationAccessGrant]:
        if not 1 <= limit <= 100:
            raise ValueError("Verification access page size must be between 1 and 100")
        return [
            stored.grant for stored in await self._repository.list(owner, after=after, limit=limit)
        ]

    async def revoke(self, grant_id: str, owner: Identity) -> None:
        stored = await self._repository.get(grant_id)
        if stored is None or not stored.grant.owner.owns(owner):
            raise VerificationMissing("Verification access not found")
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
            expiry = grant.renewal.next_expiry(now, grant.expires_at) if grant.renewal else None
            if grant.revoked:
                continue
            if grant.expires_at <= now:
                await self._repository.expire(grant.grant_id, grant.expires_at, now=now)
                continue
            if not self._permitted(grant.scope, grant.owner):
                await self._repository.revoke(grant.grant_id)
                continue
            try:
                if expiry is None:
                    if await self._executions.closed(grant.scope.root_execution_id, grant.owner):
                        await self._repository.revoke(grant.grant_id)
                    continue
                active = await self._executions.active(grant.scope.root_execution_id, grant.owner)
                if active:
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
