from flareward.programs.graph.graph_plan import GraphPlan
from flareward.programs.graph.validation.cycle.detector import CycleDetector
from flareward.programs.graph.validation.fix_models import FixSuggestion, FixType
from flareward.programs.graph.validation.interfaces import FixSuggestionProvider
from flareward.programs.graph.validation.models import MessageCode, ValidationReport


class CycleFixProvider(FixSuggestionProvider):
    """Provides fix suggestions for cycle/loop issues in the graph."""

    name = "cycle"

    def __init__(self, *args, **kwargs):
        self._detector = CycleDetector()

    def suggest_fixes(
        self, plan: GraphPlan, validation_report: ValidationReport | None = None
    ) -> list[FixSuggestion]:
        """Suggest fixes for cycle issues."""
        suggestions = []

        if not validation_report or not validation_report.details:
            return suggestions

        cycles = validation_report.details.get("cycles", [])
        if not cycles:
            return suggestions

        # Extract message codes from validation report
        message_codes = self._extract_message_codes(validation_report)

        # Analyze each cycle and suggest fixes
        for cycle_data in cycles:
            cycle_path = cycle_data.get("cycle_path", [])
            if not cycle_path:
                continue

            suggestions.extend(self._suggest_fixes_for_cycle(cycle_path, plan, message_codes))

        return suggestions

    def _extract_message_codes(self, validation_report: ValidationReport) -> dict[str, MessageCode]:
        """Extract message codes from validation report."""
        codes = {}
        for message in validation_report.messages:
            if message.code:
                # Use cycle path as key if available
                cycle_path = message.context.get("cycle_path", [])
                key = "->".join(cycle_path) if cycle_path else "general"
                codes[key] = message.code
        return codes

    def _suggest_fixes_for_cycle(
        self, cycle_path: list[str], plan: GraphPlan, message_codes: dict[str, MessageCode]
    ) -> list[FixSuggestion]:
        """Suggest specific fixes for a detected cycle."""
        suggestions = []

        if len(cycle_path) < 2:
            return suggestions

        # Normalize cycle path (remove duplicate last element if present)
        if len(cycle_path) > 1 and cycle_path[0] == cycle_path[-1]:
            normalized_path = cycle_path[:-1]
        else:
            normalized_path = cycle_path

        # Analyze the cycle to determine fix strategies
        edge_types = self._analyze_cycle_edges(normalized_path, plan)
        cycle_key = "->".join(cycle_path)

        # Strategy 1: Remove branch connections that create cycles
        branch_suggestions = self._suggest_branch_fixes(
            normalized_path,
            edge_types,
            plan,
            message_codes.get(cycle_key, MessageCode.CYCLE_DETECTED),
        )
        suggestions.extend(branch_suggestions)

        # Strategy 2: Break dependency chains if unconditional cycles exist
        dependency_suggestions = self._suggest_dependency_fixes(
            normalized_path,
            edge_types,
            plan,
            message_codes.get(cycle_key, MessageCode.CYCLE_DETECTED),
        )
        suggestions.extend(dependency_suggestions)

        # Strategy 3: Add terminal nodes to provide exit paths
        exit_suggestions = self._suggest_exit_path_fixes(
            normalized_path, plan, message_codes.get(cycle_key, MessageCode.CYCLE_DETECTED)
        )
        suggestions.extend(exit_suggestions)

        return suggestions

    def _analyze_cycle_edges(
        self, cycle_path: list[str], plan: GraphPlan
    ) -> dict[tuple[str, str], str]:
        """Analyze edge types in the cycle."""
        edge_types = {}

        for i in range(len(cycle_path)):
            current = cycle_path[i]
            next_step = cycle_path[(i + 1) % len(cycle_path)]

            current_step = plan.get_step(current)
            if not current_step:
                continue

            # Check if it's a dependency edge (after)
            next_step_obj = plan.get_step(next_step)
            if next_step_obj is not None and current in next_step_obj.after:
                edge_types[(current, next_step)] = "after"
            # Check if it's a branch edge
            elif next_step in current_step.branches.values():
                edge_types[(current, next_step)] = "branch"
            else:
                # This might be an indirect connection
                edge_types[(current, next_step)] = "unknown"

        return edge_types

    def _suggest_branch_fixes(
        self,
        cycle_path: list[str],
        edge_types: dict[tuple[str, str], str],
        plan: GraphPlan,
        message_code: MessageCode,
    ) -> list[FixSuggestion]:
        """Suggest removing or redirecting branch connections."""
        suggestions = []

        for i in range(len(cycle_path)):
            current = cycle_path[i]
            next_step = cycle_path[(i + 1) % len(cycle_path)]
            edge_key = (current, next_step)

            if edge_types.get(edge_key) == "branch":
                current_step = plan.get_step(current)
                if current_step:
                    # Find which branch condition leads to the cycle
                    branch_name = None
                    for branch, target in current_step.branches.items():
                        if target == next_step:
                            branch_name = branch
                            break

                    step_name = (
                        current_step.meta.display_name
                        if current_step.meta.display_name
                        else current
                    )

                    if branch_name:
                        suggestions.append(
                            FixSuggestion(
                                text=(
                                    f"Remove or redirect the '{branch_name}' branch from "
                                    f"'{step_name}' step to break the cycle"
                                ),
                                fix_type=FixType.MODIFY_CONNECTION,
                                code=message_code,
                                context={
                                    "cycle_path": cycle_path,
                                    "step_id": current,
                                    "step_name": step_name,
                                    "branch_name": branch_name,
                                    "target_step": next_step,
                                    "fix_type": "remove_branch",
                                },
                                priority=2,
                            )
                        )
                    else:
                        suggestions.append(
                            FixSuggestion(
                                text=(
                                    f"Review and redirect branches from '{step_name}' step "
                                    f"to break the cycle"
                                ),
                                fix_type=FixType.MODIFY_CONNECTION,
                                code=message_code,
                                context={
                                    "cycle_path": cycle_path,
                                    "step_id": current,
                                    "step_name": step_name,
                                    "target_step": next_step,
                                    "fix_type": "review_branches",
                                },
                                priority=2,
                            )
                        )

        return suggestions

    def _suggest_dependency_fixes(
        self,
        cycle_path: list[str],
        edge_types: dict[tuple[str, str], str],
        plan: GraphPlan,
        message_code: MessageCode,
    ) -> list[FixSuggestion]:
        """Suggest breaking dependency chains that create unconditional cycles."""
        suggestions = []

        # Look for dependency edges in the cycle
        for i in range(len(cycle_path)):
            current = cycle_path[i]
            next_step = cycle_path[(i + 1) % len(cycle_path)]
            edge_key = (current, next_step)

            if edge_types.get(edge_key) == "after":
                current_step = plan.get_step(current)
                next_step_obj = plan.get_step(next_step)

                if current_step and next_step_obj:
                    current_name = (
                        current_step.meta.display_name
                        if current_step.meta.display_name
                        else current
                    )
                    next_name = (
                        next_step_obj.meta.display_name
                        if next_step_obj.meta.display_name
                        else next_step
                    )

                    suggestions.append(
                        FixSuggestion(
                            text=(
                                f"Remove the dependency from '{next_name}' on "
                                f"'{current_name}' to break the unconditional cycle"
                            ),
                            fix_type=FixType.MODIFY_CONNECTION,
                            code=message_code,
                            context={
                                "cycle_path": cycle_path,
                                "dependent_step": next_step,
                                "dependency_step": current,
                                "dependent_step_name": next_name,
                                "dependency_step_name": current_name,
                                "fix_type": "remove_dependency",
                            },
                            priority=3,  # High priority - unconditional cycles are dangerous
                        )
                    )

        return suggestions

    def _suggest_exit_path_fixes(
        self, cycle_path: list[str], plan: GraphPlan, message_code: MessageCode
    ) -> list[FixSuggestion]:
        """Suggest adding nodes or connections to provide exit paths from the cycle."""
        suggestions = []

        # Suggest adding a terminal node that cycle nodes can branch to
        cycle_display_names = []
        for step_id in cycle_path:
            step = plan.get_step(step_id)
            if step:
                name = step.meta.display_name if step.meta.display_name else step_id
                cycle_display_names.append(name)

        cycle_description = " -> ".join(cycle_display_names)

        suggestions.append(
            FixSuggestion(
                text=(
                    f"Add a terminal node and create conditional branches from the cycle "
                    f"({cycle_description}) to provide an exit path"
                ),
                fix_type=FixType.ADD_NODE,
                code=message_code,
                context={
                    "cycle_path": cycle_path,
                    "cycle_steps": cycle_path,
                    "fix_type": "add_exit_node",
                    "suggested_node_category": "nodes",
                    "suggested_node_type": "final_answer_node",
                },
                priority=1,
            )
        )

        return suggestions
