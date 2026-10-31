from collections.abc import Set as AbstractSet

from mas.graph.graph_plan import GraphPlan

from ..models import MessageCode, MessageSeverity, ValidationMessage
from .models import NodePosition, RequiredNodeIssue


class RequiredNodesChecker:
    """Business logic for checking required node types and counts."""

    def __init__(
        self,
        required_start_nodes: set[str] = None,
        required_end_nodes: set[str] = None,
        required_any_nodes: set[str] = None,
        max_start_nodes: int | None = None,
        max_end_nodes: int | None = None,
        max_any_nodes: int | None = None,
    ):
        self._required_start_nodes = set(required_start_nodes or set())
        self._required_end_nodes = set(required_end_nodes or set())
        self._required_any_nodes = set(required_any_nodes or set())

        # Maximum node constraints
        self._max_start_nodes = max_start_nodes
        self._max_end_nodes = max_end_nodes
        self._max_any_nodes = max_any_nodes

    def check_required_nodes(
        self, plan: GraphPlan
    ) -> tuple[list[RequiredNodeIssue], list[ValidationMessage]]:
        """Check that required node types are present and within limits."""
        messages = []
        required_node_issues = []

        # Get node collections
        roots = plan.get_roots()
        leaves = plan.get_leaves()
        all_steps = plan.steps

        # Get node type sets (for min checks)
        root_types = {s.type_key for s in roots}
        leaf_types = {s.type_key for s in leaves}
        all_types = {s.type_key for s in all_steps}

        # Check MINIMUM requirements (existing)
        self._check_nodes(
            self._required_start_nodes,
            root_types,
            NodePosition.START,
            MessageCode.MISSING_START_NODE,
            messages,
            required_node_issues,
        )

        self._check_nodes(
            self._required_end_nodes,
            leaf_types,
            NodePosition.END,
            MessageCode.MISSING_END_NODE,
            messages,
            required_node_issues,
        )

        self._check_nodes(
            self._required_any_nodes,
            all_types,
            NodePosition.ANY,
            MessageCode.MISSING_REQUIRED_NODE,
            messages,
            required_node_issues,
        )

        # Check MAXIMUM constraints
        self._check_max_nodes(
            len(roots),
            self._max_start_nodes,
            NodePosition.START,
            MessageCode.TOO_MANY_START_NODES,
            messages,
            required_node_issues,
        )

        self._check_max_nodes(
            len(leaves),
            self._max_end_nodes,
            NodePosition.END,
            MessageCode.TOO_MANY_END_NODES,
            messages,
            required_node_issues,
        )

        self._check_max_nodes(
            len(all_steps),
            self._max_any_nodes,
            NodePosition.ANY,
            MessageCode.TOO_MANY_NODES,
            messages,
            required_node_issues,
        )

        return required_node_issues, messages

    def _check_nodes(
        self,
        required_specs: AbstractSet[str],
        available_specs: AbstractSet[str],
        node_type: NodePosition,
        error_code: MessageCode,
        messages: list[ValidationMessage],
        required_node_issues: list[RequiredNodeIssue],
    ) -> None:
        """Check for missing required nodes."""
        for spec in required_specs - available_specs:
            required_node_issues.append(
                RequiredNodeIssue(
                    node_type=node_type,
                    expected=spec,
                    actual=None if not available_specs else next(iter(available_specs)),
                )
            )

            verb = {"start": "start with", "end": "end with", "any": "contain"}[node_type]
            messages.append(
                ValidationMessage(
                    text=f"Graph must {verb} '{spec}' node",
                    severity=MessageSeverity.ERROR,
                    code=error_code,
                    context={"expected": spec, "available": list(available_specs)},
                )
            )

    def _check_max_nodes(
        self,
        actual_count: int,
        max_count: int | None,
        node_type: NodePosition,
        error_code: MessageCode,
        messages: list[ValidationMessage],
        required_node_issues: list[RequiredNodeIssue],
    ) -> None:
        """Check if node count exceeds maximum."""
        if max_count is None:
            return  # No limit set

        if actual_count > max_count:
            position_name = {"start": "start", "end": "end", "any": "total"}[node_type]

            required_node_issues.append(
                RequiredNodeIssue(
                    node_type=node_type, expected=f"max {max_count}", actual=str(actual_count)
                )
            )

            messages.append(
                ValidationMessage(
                    text=(
                        f"Graph has too many {position_name} nodes: {actual_count} (max "
                        f"allowed: {max_count})"
                    ),
                    severity=MessageSeverity.ERROR,
                    code=error_code,
                    context={
                        "actual_count": actual_count,
                        "max_allowed": max_count,
                        "position": node_type,
                    },
                )
            )
