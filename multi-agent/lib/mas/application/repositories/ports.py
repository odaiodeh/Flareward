"""Application-owned repository capabilities; no Git process or filesystem handles."""

from typing import Protocol

from mas.domain.execution.context import ExecutionContext
from mas.domain.repositories import GitRevision


class RepositoryError(RuntimeError):
    """Repository access failed, with safe diagnostics independent of the transport."""


class RepositoryConflict(ValueError):
    """An existing workspace must not be replaced by source materialization."""


class GitRepository(Protocol):
    async def resolve(self, reference: str) -> GitRevision: ...

    async def checkout(
        self, revision: GitRevision, workspace: str, context: ExecutionContext
    ) -> None: ...
