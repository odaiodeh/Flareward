"""Shared issuance data and ports for both renewable workflow credential purposes."""

import asyncio
from dataclasses import dataclass

from pydantic import SecretStr

from flareward.services.access.issuance import (
    CredentialDelivery,
    CredentialIssuance,
    CredentialMaterialStore,
)
from flareward.services.identity.domain import Identity
from flareward.services.reviews.access import (
    ReviewAccessRepository,
    ReviewAccessRequest,
    ReviewAccessService,
    ReviewAction,
    ReviewGrant,
    ReviewScope,
)
from flareward.services.verification.access import VerificationAccessService
from flareward.services.verification.access_models import (
    VerificationAccessGrant,
    VerificationAccessRequest,
    VerificationAccessScope,
    VerificationAction,
)
from flareward.services.verification.ports import VerificationAccessRepository
from support.execution_access import ExecutionAuthority
from support.reviews import MemoryReviewAccess, review_policy
from support.verification import (
    MemoryVerificationAccessRepository,
    VerificationClock,
    verification_policy,
)


@dataclass(frozen=True)
class RenewalCase:
    service: ReviewAccessService | VerificationAccessService
    repository: ReviewAccessRepository | VerificationAccessRepository
    grant: ReviewGrant | VerificationAccessGrant
    credential: SecretStr
    clock: VerificationClock
    authority: ExecutionAuthority
    request: ReviewAccessRequest | VerificationAccessRequest

    @classmethod
    async def create(
        cls,
        purpose: str,
        *,
        clock: VerificationClock | None = None,
        review_repository: ReviewAccessRepository | None = None,
        verification_repository: VerificationAccessRepository | None = None,
        renewable: bool = True,
        material_store: CredentialMaterialStore | None = None,
        delivery: CredentialDelivery | None = None,
        key: str | None = None,
        owner: Identity | None = None,
        issued_by: Identity | None = None,
    ) -> RenewalCase:
        now = clock if clock is not None else VerificationClock()
        owner = owner if owner is not None else Identity.user("owner")
        issued_by = issued_by if issued_by is not None else owner
        authority = ExecutionAuthority()
        if purpose == "review":
            reviews = review_repository if review_repository is not None else MemoryReviewAccess()
            service = ReviewAccessService(
                reviews,
                {"release@1": review_policy(owner)},
                execution_authority=authority,
                clock=now,
                issuance=CredentialIssuance(ReviewAccessService.purpose, material_store, delivery)
                if material_store is not None
                else None,
            )
            request = ReviewAccessRequest(
                scope=ReviewScope(
                    root_execution_id="root",
                    policies=frozenset({"release@1"}),
                    actions=frozenset(ReviewAction),
                ),
                ttl_seconds=60,
                renewable_for_seconds=180 if renewable else None,
            )
            grant, credential = await service.issue(request, owner, issued_by, key=key)
            return cls(service, reviews, grant, credential, now, authority, request)
        verifications = (
            verification_repository
            if verification_repository is not None
            else MemoryVerificationAccessRepository()
        )
        verification_service = VerificationAccessService(
            verifications,
            {"release@1": verification_policy(owner)},
            execution_authority=authority,
            clock=now,
            issuance=CredentialIssuance(VerificationAccessService.purpose, material_store, delivery)
            if material_store is not None
            else None,
        )
        verification_request = VerificationAccessRequest(
            scope=VerificationAccessScope(
                root_execution_id="root",
                policies=frozenset({"release@1"}),
                actions=frozenset(VerificationAction),
            ),
            ttl_seconds=60,
            renewable_for_seconds=180 if renewable else None,
        )
        issued = await verification_service.issue(verification_request, owner, issued_by, key=key)
        return cls(
            verification_service,
            verifications,
            issued.grant,
            issued.credential,
            now,
            authority,
            verification_request,
        )

    async def reissue(
        self,
        key: str | None,
        *,
        request: ReviewAccessRequest | VerificationAccessRequest | None = None,
        issued_by: Identity | None = None,
    ) -> tuple[ReviewGrant | VerificationAccessGrant, SecretStr]:
        request = request if request is not None else self.request
        actor = issued_by if issued_by is not None else self.grant.issued_by
        if isinstance(self.service, ReviewAccessService):
            assert isinstance(request, ReviewAccessRequest)
            return await self.service.issue(request, self.grant.owner, actor, key=key)
        assert isinstance(request, VerificationAccessRequest)
        issued = await self.service.issue(request, self.grant.owner, actor, key=key)
        return issued.grant, issued.credential


async def retired_credential(
    repository: ReviewAccessRepository | VerificationAccessRepository, grant_id: str
) -> ReviewGrant | VerificationAccessGrant:
    async with asyncio.timeout(10):
        while True:
            stored = await repository.get(grant_id)
            if stored is not None and stored.grant.revoked:
                return stored.grant
            await asyncio.sleep(0.05)
