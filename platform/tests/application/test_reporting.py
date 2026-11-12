"""Reporting authorization and derived business semantics depend on owned ports."""

import asyncio
from unittest.mock import create_autospec

import pytest
from support.program_interfaces import declared_interface
from support.reporting import NOW, OWNER, TEAM

from lumora.programs.domain.models import (
    CustomCoordinatorDefinition,
    ProgramDefinition,
    ProgramRef,
    ProgramRevision,
)
from lumora.programs.ports import ProgramRepository
from lumora.services.access.administrators import (
    AdministratorAccessUnavailable,
    AdministratorDirectory,
    AdministratorPolicy,
)
from lumora.services.identity.domain import Identity
from lumora.services.reporting.models import ProgramUsage, SystemReport, TimeRange
from lumora.services.reporting.service import (
    ReportingReader,
    ReportingService,
    ReportingUnavailable,
)


def system_report(*usages: ProgramUsage) -> SystemReport:
    return SystemReport(
        root_executions=4,
        unique_owners=1,
        programs_used=1,
        status_breakdown={"completed": 2, "cancelled": 1, "running": 1},
        owner_activity=(),
        top_owners=(),
        owner_offset=0,
        owner_limit=10,
        top_programs=usages,
        time_series=(),
        time_series_truncated=False,
        generated_at=NOW,
    )


@pytest.mark.parametrize(
    "persisted,expected", [(None, True), ((), False), (("SAME",), True), (("other",), False)]
)
async def test_administrator_directory_is_authoritative(persisted, expected):
    directory = create_autospec(AdministratorDirectory, instance=True)
    directory.usernames.return_value = persisted
    policy = AdministratorPolicy(directory, ("same",))
    assert await policy.allowed(OWNER) is expected
    assert not await policy.allowed(TEAM)


async def test_directory_failure_never_restores_bootstrap_authority():
    directory = create_autospec(AdministratorDirectory, instance=True)
    directory.usernames.side_effect = AdministratorAccessUnavailable()
    with pytest.raises(AdministratorAccessUnavailable):
        await AdministratorPolicy(directory, ("same",)).allowed(OWNER)


async def test_reporting_uses_human_authority_and_the_executed_revision_name():
    directory = create_autospec(AdministratorDirectory, instance=True)
    directory.usernames.return_value = ("same",)
    reader = create_autospec(ReportingReader, instance=True)
    programs = create_autospec(ProgramRepository, instance=True)
    reference = ProgramRef(program_id="build", revision=1)
    reader.system.return_value = system_report(
        ProgramUsage(
            program=reference,
            run_count=4,
            status_breakdown={"completed": 2, "cancelled": 1, "running": 1},
        )
    )
    programs.get_revision.return_value = ProgramRevision(
        definition=ProgramDefinition(
            program_id="build",
            name="Pinned name",
            owner=OWNER,
            implementation=CustomCoordinatorDefinition(implementation="wait", version="1"),
        ),
        revision=1,
        interface=declared_interface(
            ProgramDefinition(
                program_id="build",
                name="Pinned name",
                owner=OWNER,
                implementation=CustomCoordinatorDefinition(implementation="wait", version="1"),
            )
        ),
    )
    service = ReportingService(reader, AdministratorPolicy(directory), programs, clock=lambda: NOW)
    with pytest.raises(PermissionError):
        await service.system(Identity.user("other"), TimeRange.ALL)
    with pytest.raises(PermissionError):
        await service.system(TEAM, TimeRange.ALL)
    reader.system.assert_not_awaited()
    report = await service.system(OWNER, TimeRange.TODAY, limit=10)
    assert report.top_programs[0].program_name == "Pinned name"
    assert report.top_programs[0].completion_rate == 66.7
    programs.get_revision.assert_awaited_once_with(reference)
    reader.system.assert_awaited_once_with(NOW.replace(hour=0), NOW, offset=0, limit=10)


@pytest.mark.parametrize("cancel", (False, True))
async def test_reporting_drains_parallel_lookups_before_failure_or_cancellation(cancel):
    directory = create_autospec(AdministratorDirectory, instance=True)
    directory.usernames.return_value = ("same",)
    reader = create_autospec(ReportingReader, instance=True)
    programs = create_autospec(ProgramRepository, instance=True)
    reader.system.return_value = system_report(
        *(
            ProgramUsage(
                program=ProgramRef(program_id="build", revision=revision),
                run_count=1,
                status_breakdown={"running": 1},
            )
            for revision in (1, 2)
        )
    )
    both_started, hold = asyncio.Event(), asyncio.Event()
    started, finished = set(), set()

    async def lookup(reference):
        started.add(reference.revision)
        if len(started) == 2:
            both_started.set()
        try:
            await both_started.wait()
            if not cancel and reference.revision == 1:
                raise RuntimeError("private database failure")
            await hold.wait()
        finally:
            finished.add(reference.revision)

    programs.get_revision.side_effect = lookup
    service = ReportingService(reader, AdministratorPolicy(directory), programs, clock=lambda: NOW)
    async with asyncio.timeout(5):
        task = asyncio.create_task(service.system(OWNER, TimeRange.ALL))
        try:
            await both_started.wait()
            if cancel:
                task.cancel()
                with pytest.raises(asyncio.CancelledError):
                    await task
            else:
                with pytest.raises(ReportingUnavailable, match="^Reporting is unavailable$"):
                    await task
            assert finished == {1, 2}
        finally:
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
