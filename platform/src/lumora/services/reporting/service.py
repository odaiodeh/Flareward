"""Reporting use cases own authorization, time scope and pinned publication labels."""

import asyncio
from collections.abc import Callable
from datetime import UTC, datetime
from functools import partial
from typing import Protocol

from lumora.executions.domain.models import ExecutionPhase
from lumora.programs.ports import ProgramRepository
from lumora.services.access.administrators import AdministratorAccess
from lumora.services.identity.domain import Identity
from lumora.services.reporting.models import OwnerOverview, ProgramUsage, SystemReport, TimeRange


class ReportingUnavailable(RuntimeError):
    def __init__(self) -> None:
        super().__init__("Reporting is unavailable")


class ReportingReader(Protocol):
    async def overview(self, owner: Identity) -> OwnerOverview: ...
    async def system(
        self, since: datetime | None, until: datetime, *, offset: int, limit: int
    ) -> SystemReport: ...


class ReportingService:
    def __init__(
        self,
        reader: ReportingReader,
        administrators: AdministratorAccess,
        programs: ProgramRepository,
        *,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._reader, self._administrators, self._programs = reader, administrators, programs
        self._now = clock or partial(datetime.now, UTC)

    async def overview(self, owner: Identity) -> OwnerOverview:
        if not owner.id:
            raise PermissionError("Reporting requires an owner")
        return await self._reader.overview(owner)

    async def system(
        self, user: Identity, time_range: TimeRange, *, offset: int = 0, limit: int = 100
    ) -> SystemReport:
        if not user.is_user or not user.id or not await self._administrators.allowed(user):
            raise PermissionError("Administrator access is required")
        if offset < 0 or not 1 <= limit <= 100:
            raise ValueError("Invalid reporting page")
        now = self._now()
        report = await self._reader.system(time_range.since(now), now, offset=offset, limit=limit)

        try:
            async with asyncio.TaskGroup() as group:
                views = [group.create_task(self._program_view(row)) for row in report.top_programs]
        except ExceptionGroup:
            raise ReportingUnavailable() from None
        return report.model_copy(update={"top_programs": tuple(view.result() for view in views)})

    async def _program_view(self, row: ProgramUsage) -> ProgramUsage:
        name = None
        try:
            revision = await self._programs.get_revision(row.program)
            name = revision.definition.name
        except KeyError:
            pass
        terminal = sum(
            row.status_breakdown.get(phase, 0)
            for phase in (ExecutionPhase.COMPLETED, ExecutionPhase.FAILED, ExecutionPhase.CANCELLED)
        )
        rate = (
            round(100 * row.status_breakdown.get(ExecutionPhase.COMPLETED, 0) / terminal, 1)
            if terminal
            else None
        )
        return row.model_copy(update={"program_name": name, "completion_rate": rate})
