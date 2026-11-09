"""Ownership, lineage access, byte admission, and stable publication identities."""

import hashlib
import json
from collections.abc import AsyncIterable, AsyncIterator
from contextlib import asynccontextmanager

from flareward.services.artifacts.access_models import ArtifactAction, ArtifactActor
from flareward.services.artifacts.domain.models import (
    ArtifactRecord,
    BlobArtifactRef,
    PublishArtifact,
)
from flareward.services.artifacts.ports import (
    ArtifactIntegrityError,
    ArtifactLimitExceeded,
    ArtifactMissing,
    ArtifactRepository,
)


class ArtifactService:
    def __init__(self, repository: ArtifactRepository, *, max_bytes: int = 67_108_864) -> None:
        if max_bytes < 1:
            raise ValueError("Artifact byte limit must be positive")
        self._repository, self._max_bytes = repository, max_bytes

    async def publish(
        self, request: PublishArtifact, content: AsyncIterable[bytes], caller: ArtifactActor
    ) -> ArtifactRecord:
        owner = caller.identity.model_copy(deep=True)
        if caller.scope is not None and not caller.scope.allows(
            ArtifactAction.PUBLISH, request.namespace
        ):
            raise PermissionError("Artifact publication is not permitted")
        limit = min(self._max_bytes, caller.scope.max_bytes) if caller.scope else self._max_bytes
        if request.size_bytes > limit:
            raise ArtifactLimitExceeded("Artifact exceeds its byte limit")
        for source in request.inputs:
            record = await self.inspect(source.artifact_id, caller)
            if record.reference != source:
                raise ArtifactIntegrityError("Input artifact identity does not match")
        scope = json.dumps(
            [owner.type.value, owner.id, request.namespace, request.key], separators=(",", ":")
        )
        reference = BlobArtifactRef(
            artifact_id=hashlib.sha256(scope.encode()).hexdigest(),
            sha256=request.sha256,
            size_bytes=request.size_bytes,
        )
        record = ArtifactRecord(
            reference=reference,
            owner=owner,
            namespace=request.namespace,
            name=request.name,
            media_type=request.media_type,
            inputs=request.inputs,
        )
        return await self._repository.put(record, content)

    async def inspect(self, artifact_id: str, caller: ArtifactActor) -> ArtifactRecord:
        record = await self._repository.get(artifact_id)
        if not record.owner.owns(caller.identity) or (
            caller.scope is not None
            and not caller.scope.allows(ArtifactAction.READ, record.namespace, artifact_id)
        ):
            raise ArtifactMissing("Artifact not found")
        return record

    @asynccontextmanager
    async def open(
        self, reference: BlobArtifactRef, caller: ArtifactActor
    ) -> AsyncIterator[AsyncIterator[bytes]]:
        record = await self.download(reference.artifact_id, caller)
        if record.reference != reference:
            raise ArtifactIntegrityError("Artifact identity does not match")
        async with self._repository.open(reference) as content:
            yield content

    async def download(self, artifact_id: str, caller: ArtifactActor) -> ArtifactRecord:
        """Admit content transfer before opening an HTTP response or storage stream."""
        record = await self.inspect(artifact_id, caller)
        if caller.scope is not None and record.reference.size_bytes > caller.scope.max_bytes:
            raise ArtifactLimitExceeded("Artifact download exceeds its byte limit")
        return record
