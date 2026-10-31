"""Phase-related protocols and models for agent strategies."""

from dataclasses import dataclass

# Forward declaration for AgentObservation
from typing import TYPE_CHECKING, Any, Protocol

# Import ExecutionPhase for stronger typing
from mas.application.agents.constants import ExecutionPhase
from mas.application.ports.tool import BaseTool

# Import WorkPlanStatus from workload layer (single source of truth)
from mas.domain.workloads import WorkPlanStatus

if TYPE_CHECKING:
    from mas.domain.agents import AgentObservation


# =============================================================================
# PHASE STATE MODELS
# =============================================================================
# Note: WorkPlanStatus is now imported from workload layer (single source of truth)


@dataclass(frozen=True)
class PhaseState:
    """Immutable state information for phase decision making."""

    work_plan_status: WorkPlanStatus | None = None
    thread_id: str | None = None
    node_uid: str | None = None
    additional_context: dict[str, Any] | None = None


# =============================================================================
# PROTOCOLS
# =============================================================================


class PhaseContextProvider(Protocol):
    """Protocol for providing phase context to strategies."""

    def get_phase_context(self) -> PhaseState:
        """Get current phase context for decision making."""
        ...


class PhaseToolProvider(Protocol):
    """Protocol for providing phase-specific tools to strategies."""

    def get_tools_for_phase(self, phase: ExecutionPhase) -> list[BaseTool]:
        """Get tools appropriate for the given phase."""
        ...

    def get_all_phase_tools(self) -> dict[ExecutionPhase, list[BaseTool]]:
        """Get all phase-to-tools mappings."""
        ...


class PhaseTransitionPolicy(Protocol):
    """Protocol for determining phase transitions in strategies."""

    def decide(
        self, *, state: PhaseState, current: ExecutionPhase, observations: list[AgentObservation]
    ) -> ExecutionPhase:
        """Decide the next execution phase based on current state."""
        ...


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================
# Note: create_work_plan_status() removed - use WorkPlanStatus() directly from workload layer


def create_phase_state(
    work_plan_status: WorkPlanStatus | None = None,
    thread_id: str | None = None,
    node_uid: str | None = None,
    **additional_context: Any,
) -> PhaseState:
    """Create a PhaseState with optional additional context."""
    return PhaseState(
        work_plan_status=work_plan_status,
        thread_id=thread_id,
        node_uid=node_uid,
        additional_context=additional_context if additional_context else None,
    )
