"""Shared schedule requests use only application contracts."""

from datetime import timedelta

from mas.programs.models import PathBinding, ProgramRef
from mas.scheduling.models import ScheduleDefinition
from mas.scheduling.programs import CreateProgramSchedule
from mas.session.execution.program_sessions import CreateProgramSession


def schedule_request(program: ProgramRef, *, enabled: bool = False) -> CreateProgramSchedule:
    return CreateProgramSchedule(
        session=CreateProgramSession(
            program=program,
            output_bindings={"output": PathBinding(path=("answer",))},
        ),
        inputs={"name": "scheduled"},
        schedule=ScheduleDefinition(interval=timedelta(days=1), enabled=enabled),
    )
