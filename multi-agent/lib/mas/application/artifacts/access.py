"""Issue, inspect, revoke and authenticate owner-bound artifact capabilities."""

from datetime import UTC, datetime, timedelta

from mas.application.access.credentials import OpaqueCredentials
from mas.application.artifacts.access_models import (
    ArtifactAccessGrant,
    ArtifactAccessRequest,
    IssuedArtifactAccess,
    StoredArtifactAccess,
)
from mas.application.artifacts.ports import (
    ArtifactAccessRepository,
    ArtifactCredentialError,
    ArtifactLimitExceeded,
    ArtifactMissing,
)
from mas.core.identity import Identity


class ArtifactAccessService:
    def __init__(
        self, repository: ArtifactAccessRepository, *, max_bytes: int = 67_108_864
    ) -> None:
        self._repository, self._max_bytes = repository, max_bytes
        self._credentials = OpaqueCredentials("unifai-artifact-v1")

    async def issue(self, request: ArtifactAccessRequest, caller: Identity) -> IssuedArtifactAccess:
        if request.scope.max_bytes > self._max_bytes:
            raise ArtifactLimitExceeded("Artifact access exceeds the configured byte limit")
        now = datetime.now(UTC)
        credential = self._credentials.issue()
        grant = ArtifactAccessGrant(
            grant_id=credential.identifier,
            owner=caller.model_copy(deep=True),
            scope=request.scope,
            issued_at=now,
            expires_at=now + timedelta(seconds=request.ttl_seconds),
        )
        await self._repository.create(
            StoredArtifactAccess(grant=grant, secret_sha256=credential.sha256)
        )
        return IssuedArtifactAccess(grant, credential.secret)

    async def authenticate(self, credential: str) -> ArtifactAccessGrant:
        identifier = self._credentials.identify(credential)
        stored = await self._repository.get(identifier) if identifier is not None else None
        if (
            stored is None
            or stored.grant.revoked
            or stored.grant.expires_at <= datetime.now(UTC)
            or not self._credentials.matches(credential, stored.secret_sha256)
        ):
            raise ArtifactCredentialError("Invalid artifact credential")
        return stored.grant

    async def list(
        self, caller: Identity, *, after: str = "", limit: int = 100
    ) -> list[ArtifactAccessGrant]:
        if not 1 <= limit <= 100:
            raise ValueError("Artifact access page size must be between 1 and 100")
        return [
            stored.grant for stored in await self._repository.list(caller, after=after, limit=limit)
        ]

    async def revoke(self, grant_id: str, caller: Identity) -> None:
        stored = await self._repository.get(grant_id)
        if stored is None or not stored.grant.owner.owns(caller):
            raise ArtifactMissing("Artifact access not found")
        await self._repository.revoke(grant_id)
