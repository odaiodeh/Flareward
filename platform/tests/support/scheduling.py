"""Shared schedule requests use only application contracts."""

from datetime import timedelta

from lumora.programs.domain.models import PathBinding, ProgramRef
from lumora.services.scheduling.models import ScheduleDefinition
from lumora.services.scheduling.programs import CreateProgramSchedule
from lumora.services.sessions.execution.program_sessions import CreateProgramSession


def schedule_request(program: ProgramRef, *, enabled: bool = False) -> CreateProgramSchedule:
    return CreateProgramSchedule(
        session=CreateProgramSession(
            program=program,
            output_bindings={"output": PathBinding(path=("answer",))},
        ),
        inputs={"name": "scheduled"},
        schedule=ScheduleDefinition(interval=timedelta(days=1), enabled=enabled),
    )
