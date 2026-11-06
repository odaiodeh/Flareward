"""Portable reporting fixtures separate executions, sessions, identities and revisions."""

from datetime import UTC, datetime, timedelta

from mas.core.identity import Identity
from mas.domain.execution.context import ExecutionContext
from mas.domain.execution.models import ExecutionPhase, ExecutionRecord
from mas.domain.programs.models import ProgramRef

NOW = datetime(2026, 11, 5, 12, tzinfo=UTC)
OWNER = Identity.user("same")
TEAM = Identity.team("same")


def execution(
    key: str, owner=OWNER, *, phase=ExecutionPhase.COMPLETED, revision=1, at=NOW, parent=None
):
    return ExecutionRecord(
        execution_id=key,
        owner=owner,
        program=ProgramRef(program_id="build", revision=revision),
        parent_execution_id=parent,
        phase=phase,
        submission="accepted",
        inputs={"private": "reporting-private-sentinel"},
        context=ExecutionContext(
            identity=owner,
            execution_id=key,
            root_execution_id=parent or key,
            parent_execution_id=parent,
            ancestor_execution_ids=(parent,) if parent else (),
            started_at=at,
            finished_at=at + timedelta(seconds=10) if phase == ExecutionPhase.COMPLETED else None,
        ),
    )


def executions() -> tuple[ExecutionRecord, ...]:
    return (
        execution("first"),
        execution("second"),
        execution("failed", phase=ExecutionPhase.FAILED, revision=2),
        execution("running", phase=ExecutionPhase.RUNNING),
        execution("team", TEAM, phase=ExecutionPhase.CANCELLED),
        execution("child", parent="first"),
        execution("old", at=NOW - timedelta(days=40)),
    )
