"""Translate native lifecycle values at the engine boundary."""

from mas.domain.execution.models import ExecutionPhase
from runengine.coordination.enums import RunPhase


def execution_phase(phase: RunPhase) -> ExecutionPhase:
    return {
        RunPhase.RUNNING: ExecutionPhase.RUNNING,
        RunPhase.COMPLETED: ExecutionPhase.COMPLETED,
        RunPhase.FAILED: ExecutionPhase.FAILED,
        RunPhase.CANCELLED: ExecutionPhase.CANCELLED,
        RunPhase.UNKNOWN: ExecutionPhase.UNKNOWN,
    }[phase]
