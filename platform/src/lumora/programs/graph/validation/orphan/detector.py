from lumora.programs.graph.graph_plan import GraphPlan
from lumora.programs.graph.topology.connectivity_analyzer import ConnectivityAnalyzer
from lumora.programs.graph.validation.models import (
    MessageCode,
    MessageSeverity,
    ValidationMessage,
)


class OrphanDetector:
    """Detects orphaned steps with no connections."""

    def detect_orphans(self, plan: GraphPlan) -> tuple[set[str], list[ValidationMessage]]:
        """Find steps with no dependencies or dependents."""
        messages = []

        # Use topology utilities for connectivity analysis
        connectivity_analyzer = ConnectivityAnalyzer(plan)
        orphaned_steps = connectivity_analyzer.find_orphaned_nodes()

        for orphan in orphaned_steps:
            messages.append(
                ValidationMessage(
                    text=f"Step '{orphan}' is orphaned (no dependencies or dependents)",
                    severity=MessageSeverity.WARNING,
                    code=MessageCode.ORPHANED_STEP,
                    context={"step_id": orphan},
                )
            )

        return orphaned_steps, messages
