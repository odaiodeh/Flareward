"""Async session persistence with optimistic concurrency across server replicas."""

from collections.abc import Sequence
from typing import Protocol

from pydantic import BaseModel, Field

from flareward.services.identity.domain import Identity
from flareward.services.sessions.domain.dto import SessionListFilter
from flareward.services.sessions.records import SessionRecord


class SessionPage(BaseModel):
    records: list[SessionRecord]
    total: int = Field(ge=0)
    offset: int = Field(ge=0)
    limit: int = Field(ge=1, le=100)


class SessionStore(Protocol):
    async def create(self, record: SessionRecord) -> bool: ...

    async def get(self, session_id: str) -> SessionRecord: ...

    async def replace(self, record: SessionRecord, *, expected_version: int) -> bool:
        """Replace only the observed version; the new version must increment by one."""
        ...

    async def list(self, owner: Identity, *, limit: int = 100) -> list[SessionRecord]: ...

    async def query(
        self, owner: Identity, filters: SessionListFilter, *, offset: int, limit: int
    ) -> SessionPage: ...

    async def delete(self, record: SessionRecord) -> bool:
        """Delete only the authorized record at its observed version."""
        ...

    async def scheduled(
        self, owner: Identity, schedule_id: str, *, limit: int
    ) -> Sequence[SessionRecord]: ...

    async def pending(
        self,
        *,
        limit: int = 100,
        after_session_id: str | None = None,
    ) -> Sequence[SessionRecord]: ...


class SessionConflict(ValueError):
    """The session is busy or has changed since it was read."""
