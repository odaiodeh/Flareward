from lumora.programs.graph.graph_plan import GraphPlan
from lumora.programs.graph.validation.fix_models import FixSuggestion, FixType
from lumora.programs.graph.validation.interfaces import FixSuggestionProvider
from lumora.programs.graph.validation.models import MessageCode, ValidationReport
from lumora.programs.graph.validation.orphan.detector import OrphanDetector
from lumora.programs.graph.validation.orphan.models import ConnectionType, OrphanFixType


class OrphanFixProvider(FixSuggestionProvider):
    """Provides fix suggestions for orphaned steps in the graph."""

    name = "orphan"

    def __init__(self, *args, **kwargs):
        self._detector = OrphanDetector()

    def suggest_fixes(
        self, plan: GraphPlan, validation_report: ValidationReport | None = None
    ) -> list[FixSuggestion]:
        """Suggest fixes for orphaned steps."""
        suggestions = []

        if not validation_report or not validation_report.details:
            return suggestions

        orphaned_steps = validation_report.details.get("orphaned_steps", [])
        if not orphaned_steps:
            return suggestions

        # Extract message codes from validation report
        message_codes = self._extract_message_codes(validation_report)

        # Analyze the graph structure to provide better suggestions
        connected_steps = self._get_connected_steps(plan)
        root_steps = [step.uid for step in plan.get_roots()]
        leaf_steps = [step.uid for step in plan.get_leaves()]

        # Generate suggestions for each orphaned step
        for orphan_id in orphaned_steps:
            suggestions.extend(
                self._suggest_fixes_for_orphan(
                    orphan_id, plan, connected_steps, root_steps, leaf_steps, message_codes
                )
            )

        return suggestions

    def _extract_message_codes(self, validation_report: ValidationReport) -> dict[str, MessageCode]:
        """Extract message codes from validation report."""
        codes = {}
        for message in validation_report.messages:
            if message.code:
                step_id = message.context.get("step_id", "general")
                codes[step_id] = message.code
        return codes

    def _get_connected_steps(self, plan: GraphPlan) -> list[str]:
        """Get all steps that are part of the connected graph."""
        connected = set()

        for step in plan.steps:
            if step.after or step.branches:
                connected.add(step.uid)

            # Check if other steps depend on this one
            for other in plan.steps:
                if step.uid in other.after or step.uid in other.branches.values():
                    connected.add(step.uid)

        return list(connected)

    def _suggest_fixes_for_orphan(
        self,
        orphan_id: str,
        plan: GraphPlan,
        connected_steps: list[str],
        root_steps: list[str],
        leaf_steps: list[str],
        message_codes: dict[str, MessageCode],
    ) -> list[FixSuggestion]:
        """Suggest specific fixes for an orphaned step."""
        suggestions = []

        orphan_step = plan.get_step(orphan_id)
        if not orphan_step:
            return suggestions

        orphan_name = orphan_step.meta.display_name if orphan_step.meta.display_name else orphan_id
        code = message_codes.get(orphan_id, MessageCode.ORPHANED_STEP)

        # Strategy 1: Remove the orphaned step if not needed
        suggestions.append(
            FixSuggestion(
                text=f"Remove the orphaned '{orphan_name}' step if it's not needed in the workflow",
                fix_type=FixType.REMOVE_NODE,
                code=code,
                context={
                    "step_id": orphan_id,
                    "step_name": orphan_name,
                    "fix_type": OrphanFixType.REMOVE_ORPHAN,
                },
                priority=1,  # Low priority - removing might not be desired
            )
        )

        # Strategy 2: Connect the orphan to the current workflow
        if connected_steps:
            connection_suggestions = self._get_connection_suggestions(connected_steps, plan)
            if connection_suggestions:
                step_list = ", ".join([f"'{s}'" for s in connection_suggestions[:3]])
                more_text = (
                    f" and {len(connection_suggestions) - 3} others"
                    if len(connection_suggestions) > 3
                    else ""
                )

                suggestions.append(
                    FixSuggestion(
                        text=(
                            f"Connect '{orphan_name}' to the workflow by creating "
                            f"dependencies with {step_list}{more_text}"
                        ),
                        fix_type=FixType.MODIFY_CONNECTION,
                        code=code,
                        context={
                            "step_id": orphan_id,
                            "step_name": orphan_name,
                            "fix_type": OrphanFixType.CONNECT_TO_WORKFLOW,
                            "suggested_connections": [
                                s.replace(" (display)", "") for s in connection_suggestions
                            ],
                            "connection_type": ConnectionType.DEPENDENCY,
                        },
                        priority=2,
                    )
                )

        return suggestions

    def _get_connection_suggestions(self, connected_steps: list[str], plan: GraphPlan) -> list[str]:
        """Get suggestions for steps to connect to, with display names."""
        suggestions = []

        for step_id in connected_steps[:5]:  # Limit to 5 suggestions
            step = plan.get_step(step_id)
            if step:
                name = step.meta.display_name if step.meta.display_name else step_id
                suggestions.append(name)

        return sorted(suggestions)
