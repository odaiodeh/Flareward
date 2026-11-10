"""Purpose-separated, root/policy-bound review capabilities; human decisions use sessions."""

import hashlib
import json
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from functools import partial
from typing import Protocol, Self

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    SecretStr,
    ValidationError,
    field_serializer,
    model_validator,
)

from lumora.executions.domain.access import WorkflowAccess
from lumora.services.access.catalog import WorkflowAccessDescriptor
from lumora.services.access.credentials import OpaqueCredentials
from lumora.services.access.domain.grants import WorkflowGrant
from lumora.services.access.domain.leases import CredentialLease
from lumora.services.access.executions import ExecutionAccessUnavailable, ExecutionGrantAuthority
from lumora.services.access.issuance import (
    CredentialIssuance,
    CredentialIssuanceClosed,
    CredentialMaterialUnavailable,
    CredentialStatus,
    confirmed_grant,
)
from lumora.services.identity.domain import Identity
from lumora.services.reviews.contracts import ReviewPolicy
from lumora.services.reviews.ports import ReviewCredentialError, ReviewMissing


class ReviewAction(StrEnum):
    OPEN = "open"
    READ = "read"
    CLOSE = "close"


class ReviewPermissions(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, hide_input_in_errors=True)
    policies: frozenset[str] = Field(min_length=1, max_length=32)
    actions: frozenset[ReviewAction] = Field(min_length=1)

    @field_serializer("policies", "actions")
    def ordered(self, values: frozenset[str] | frozenset[ReviewAction]) -> list[str]:
        return sorted(str(value) for value in values)

    def allows(self, action: ReviewAction, policy: str) -> bool:
        return action in self.actions and policy in self.policies


class ReviewScope(ReviewPermissions):
    root_execution_id: str = Field(min_length=1, max_length=256)


class ReviewAccessRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    scope: ReviewScope
    ttl_seconds: int = Field(default=3600, ge=1, le=2_592_000)
    renewable_for_seconds: int | None = Field(default=None, strict=True, ge=1, le=2_592_000)

    @model_validator(mode="after")
    def valid_renewal(self) -> Self:
        if self.renewable_for_seconds is not None and self.renewable_for_seconds < self.ttl_seconds:
            raise ValueError("Credential renewal horizon must cover its initial lease")
        return self


class ReviewGrant(WorkflowGrant):
    scope: ReviewScope


class StoredReviewGrant(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, hide_input_in_errors=True)
    grant: ReviewGrant
    secret_sha256: str = Field(pattern=r"^[a-f0-9]{64}$", repr=False)


@dataclass(frozen=True)
class ReviewActor:
    identity: Identity
    scope: ReviewScope | None = None


class ReviewAccessRepository(Protocol):
    async def create(self, access: StoredReviewGrant) -> None: ...
    async def ensure(self, access: StoredReviewGrant) -> StoredReviewGrant: ...
    async def get(
        self, grant_id: str, *, active_at: datetime | None = None
    ) -> StoredReviewGrant | None: ...
    async def revoke(self, grant_id: str) -> None: ...
    async def pending(self, *, after: str, limit: int) -> list[StoredReviewGrant]: ...

    async def expire(self, grant_id: str, expected_expiry: datetime, *, now: datetime) -> bool: ...
    async def renew(
        self, grant_id: str, expected_expiry: datetime, expires_at: datetime, *, now: datetime
    ) -> bool: ...


def review_credential_key(owner: Identity, root: str) -> str:
    return hashlib.sha256(
        json.dumps([owner.type.value, owner.id, root], separators=(",", ":")).encode()
    ).hexdigest()


class ReviewAccessService:
    purpose = "review@1"

    def __init__(
        self,
        repository: ReviewAccessRepository,
        policies: Mapping[str, ReviewPolicy],
        *,
        execution_authority: ExecutionGrantAuthority,
        issuance: CredentialIssuance | None = None,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._repository = repository
        if issuance is not None and issuance.purpose != self.purpose:
            raise ValueError("Review issuance purpose does not match")
        self._issuance = issuance
        self._executions = execution_authority
        self._policies = {name: policy.model_copy(deep=True) for name, policy in policies.items()}
        self._now = clock or partial(datetime.now, UTC)
        self._credentials = OpaqueCredentials("lumora-review-v1")
        self._maintenance_cursor = ""

    def describe_workflow_access(self, owner: Identity) -> WorkflowAccessDescriptor | None:
        policies = sorted(
            name
            for name, policy in self._policies.items()
            if any(allowed.owns(owner) for allowed in policy.owners)
        )
        if not policies:
            return None
        scope = ReviewPermissions.model_json_schema()
        scope["properties"]["policies"]["items"] = {"type": "string", "enum": policies}
        return WorkflowAccessDescriptor.from_models(
            self.purpose,
            "Human review requests",
            "Open, inspect or close review requests under selected policies. "
            "Human decisions remain with assigned reviewers.",
            ReviewAccessRequest,
            scope,
        )

    def _permitted(self, scope: ReviewScope, owner: Identity) -> bool:
        return all(
            name in self._policies
            and any(allowed.owns(owner) for allowed in self._policies[name].owners)
            for name in scope.policies
        )

    def _authorize(
        self, request: ReviewAccessRequest, owner: Identity, issued_by: Identity
    ) -> None:
        if (
            not owner.id
            or not issued_by.is_user
            or not issued_by.id
            or (owner.is_user and not owner.owns(issued_by))
        ):
            raise PermissionError("Review access requires authenticated human issuance")
        if not self._permitted(request.scope, owner):
            raise PermissionError("Review policy is not permitted")

    def _workflow_request(self, requirement: WorkflowAccess, root: str) -> ReviewAccessRequest:
        if requirement.purpose != self.purpose:
            raise ValueError("Workflow access purpose does not match review")
        try:
            return ReviewAccessRequest.model_validate(requirement.for_root(root))
        except ValidationError:
            raise ValueError("Workflow access violates the review scope contract") from None

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
        request: ReviewAccessRequest,
        owner: Identity,
        issued_by: Identity,
        *,
        key: str | None = None,
    ) -> tuple[ReviewGrant, SecretStr]:
        self._authorize(request, owner, issued_by)
        if await self._executions.closed(request.scope.root_execution_id, owner):
            raise PermissionError("Review access root is closed or unavailable")
        credential, now = self._credentials.issue(), self._now()
        grant = ReviewGrant(
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
        stored = StoredReviewGrant(
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
        return grant, secret

    async def credential_status(self, grant_id: str, owner: Identity) -> CredentialStatus | None:
        stored = await self._repository.get(grant_id)
        if stored is None:
            return None
        if not stored.grant.owner.owns(owner):
            raise CredentialMaterialUnavailable()
        return CredentialStatus(stored.grant.scope.root_execution_id, stored.grant.revoked)

    async def authenticate(self, credential: str) -> ReviewGrant:
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
            raise ReviewCredentialError("Invalid review credential")
        if not await self._executions.active(
            stored.grant.scope.root_execution_id, stored.grant.owner
        ):
            raise ReviewCredentialError("Invalid review credential")
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
            raise ReviewCredentialError("Invalid review credential")
        return current.grant

    async def revoke(self, grant_id: str, owner: Identity) -> None:
        stored = await self._repository.get(grant_id)
        if stored is None or not stored.grant.owner.owns(owner):
            raise ReviewMissing("Review access not found")
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
                # Keep the original expiry. Unknown authority never extends a lease.
                continue
