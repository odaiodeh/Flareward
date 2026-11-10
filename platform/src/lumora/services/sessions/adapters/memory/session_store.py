"""Detached session records for local development and application tests."""

import asyncio

from lumora.services.identity.domain import Identity
from lumora.services.sessions.domain.dto import SessionListFilter
from lumora.services.sessions.domain.status import SessionStatus
from lumora.services.sessions.execution.session_store import SessionPage
from lumora.services.sessions.records import SessionRecord


class MemorySessionStore:
    def __init__(self) -> None:
        self._records: dict[str, str] = {}
        self._lock = asyncio.Lock()

    async def create(self, record: SessionRecord) -> bool:
        async with self._lock:
            if record.run_id in self._records:
                return False
            self._records[record.run_id] = record.model_dump_json()
            return True

    async def get(self, session_id: str) -> SessionRecord:
        return SessionRecord.model_validate_json(self._records[session_id])

    async def replace(self, record: SessionRecord, *, expected_version: int) -> bool:
        if record.version != expected_version + 1:
            raise ValueError("Session version must increment by one")
        async with self._lock:
            current = await self.get(record.run_id)
            if current.version != expected_version:
                return False
            if not current.identity.owns(record.identity):
                raise ValueError("Session ownership is immutable")
            self._records[record.run_id] = record.model_dump_json()
            return True

    async def list(self, owner: Identity, *, limit: int = 100) -> list[SessionRecord]:
        records = [SessionRecord.model_validate_json(value) for value in self._records.values()]
        return [record for record in records if record.identity.owns(owner)][:limit]

    async def query(
        self, owner: Identity, filters: SessionListFilter, *, offset: int, limit: int
    ) -> SessionPage:
        records = [SessionRecord.model_validate_json(value) for value in self._records.values()]
        records = sorted(
            (
                record
                for record in records
                if record.identity.owns(owner)
                and (filters.blueprint_id is None or record.blueprint_id == filters.blueprint_id)
            ),
            key=lambda record: (record.run_context.started_at, record.run_id),
            reverse=True,
        )
        return SessionPage(
            records=records[offset : offset + limit], total=len(records), offset=offset, limit=limit
        )

    async def delete(self, record: SessionRecord) -> bool:
        async with self._lock:
            raw = self._records.get(record.run_id)
            if raw is None:
                return False
            current = SessionRecord.model_validate_json(raw)
            if current.version != record.version or not current.identity.owns(record.identity):
                return False
            del self._records[record.run_id]
            return True

    async def pending(
        self,
        *,
        limit: int = 100,
        after_session_id: str | None = None,
    ) -> list[SessionRecord]:
        records = [SessionRecord.model_validate_json(value) for value in self._records.values()]
        return [
            record
            for record in sorted(records, key=lambda value: value.run_id)
            if record.status in {SessionStatus.QUEUED, SessionStatus.RUNNING}
            and record.program is not None
            and (after_session_id is None or record.run_id > after_session_id)
        ][:limit]

    async def scheduled(
        self, owner: Identity, schedule_id: str, *, limit: int
    ) -> list[SessionRecord]:
        records = [SessionRecord.model_validate_json(value) for value in self._records.values()]
        return sorted(
            (
                record
                for record in records
                if record.identity.owns(owner) and record.metadata.schedule_id == schedule_id
            ),
            key=lambda record: record.run_context.started_at,
            reverse=True,
        )[:limit]
