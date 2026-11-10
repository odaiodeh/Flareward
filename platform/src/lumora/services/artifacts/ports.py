"""Storage guarantees are independent of filesystem, HTTP, and database technology."""

from collections.abc import AsyncIterable, AsyncIterator
from contextlib import AbstractAsyncContextManager
from dataclasses import dataclass
from typing import Protocol

from lumora.executions.domain.context import ExecutionContext
from lumora.executions.domain.models import ExecutionFailure, FailureKind
from lumora.executions.ports import ExecutionError
from lumora.services.artifacts.access_models import StoredArtifactAccess
from lumora.services.artifacts.domain.models import (
    ArtifactRecord,
    BlobArtifactRef,
    ContentIdentity,
    PublishArtifact,
)
from lumora.services.identity.domain import Identity
from lumora.services.workspaces.domain.files import WorkspaceFile


class ArtifactMissing(LookupError):
    """The artifact is missing or is not visible to the caller."""


class ArtifactConflict(ValueError):
    """A publication identity already refers to different content or metadata."""


class ArtifactIntegrityError(ValueError):
    """Declared content identity does not match the actual stored bytes."""


class ArtifactLimitExceeded(ValueError):
    """The declared or actual upload exceeds its admitted byte limit."""


class ArtifactStorageError(ExecutionError):
    """The configured artifact store is unavailable; diagnostics contain no private paths."""

    def __init__(self, message: str) -> None:
        super().__init__(
            ExecutionFailure(
                kind=FailureKind.INFRASTRUCTURE,
                message=message,
                code="artifact_storage_unavailable",
                retryable=True,
            )
        )


class ArtifactCredentialError(PermissionError):
    """Invalid, expired, or revoked artifact credentials have identical private diagnostics."""


class ArtifactAccessRepository(Protocol):
    async def create(self, access: StoredArtifactAccess) -> None: ...
    async def get(self, grant_id: str) -> StoredArtifactAccess | None: ...
    async def list(
        self, owner: Identity, *, after: str, limit: int
    ) -> list[StoredArtifactAccess]: ...
    async def revoke(self, grant_id: str) -> None: ...


class ArtifactRepository(Protocol):
    async def put(self, record: ArtifactRecord, content: AsyncIterable[bytes]) -> ArtifactRecord:
        """Atomically publish verified bytes and metadata, or retain an identical prior commit."""
        ...

    async def get(self, artifact_id: str) -> ArtifactRecord: ...
    def open(
        self, reference: BlobArtifactRef
    ) -> AbstractAsyncContextManager[AsyncIterator[bytes]]: ...


class ArtifactGateway(Protocol):
    @property
    def max_bytes(self) -> int: ...
    async def publish(
        self, request: PublishArtifact, content: AsyncIterable[bytes]
    ) -> ArtifactRecord: ...
    def open(
        self, reference: BlobArtifactRef
    ) -> AbstractAsyncContextManager[AsyncIterator[bytes]]: ...


@dataclass(frozen=True)
class FileSource:
    identity: ContentIdentity
    content: AsyncIterator[bytes]


class WorkspaceFiles(Protocol):
    def source(
        self, file: WorkspaceFile, context: ExecutionContext
    ) -> AbstractAsyncContextManager[FileSource]: ...
    async def materialize(
        self,
        file: WorkspaceFile,
        reference: ContentIdentity,
        content: AsyncIterable[bytes],
        context: ExecutionContext,
    ) -> None: ...
