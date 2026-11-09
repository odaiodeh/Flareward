from flareward.programs.graph.graph_plan import GraphPlan
from flareward.programs.graph.topology.cycle_algorithms import (
    CycleDetector as TopologyCycleDetector,
)
from flareward.programs.graph.topology.models import CycleInfo
from flareward.programs.graph.validation.models import (
    MessageCode,
    MessageSeverity,
    ValidationMessage,
)


class CycleDetector:
    """Detects cycles in graph execution flow."""

    def detect_cycles(self, plan: GraphPlan) -> tuple[list[CycleInfo], list[ValidationMessage]]:
        """Detect all cycles using topology utilities."""
        messages = []

        # Use topology utilities for cycle detection
        topology_detector = TopologyCycleDetector(plan)
        all_cycles = topology_detector.detect_all_cycles()

        # Filter for dangerous cycles using domain logic
        dangerous_cycles = []
        for cycle in all_cycles:
            if topology_detector.is_dangerous_cycle(cycle):
                dangerous_cycles.append(cycle)

        # Create validation messages
        for cycle in dangerous_cycles:
            messages.append(
                ValidationMessage(
                    text=f"Graph contains cycle: {' -> '.join(cycle.cycle_path)}",
                    severity=MessageSeverity.ERROR,
                    code=MessageCode.CYCLE_DETECTED,
                    context={"cycle_path": cycle.cycle_path, "cycle_length": cycle.cycle_length},
                )
            )

        return dangerous_cycles, messages
