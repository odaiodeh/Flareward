"""
Graph analysis utilities for working with GraphPlan.

Clean OOP design for graph topology analysis.
"""

from enum import StrEnum

from mas.graph.graph_plan import GraphPlan


class EdgeType(StrEnum):
    """Types of edges in the execution graph."""

    AFTER = "after"
    BRANCH = "branch"


class GraphAnalyzer:
    """
    Graph analyzer that works with GraphPlan objects.

    Provides clean interface for graph topology operations.
    """

    def __init__(self, plan: GraphPlan):
        self.plan = plan
        self._adjacency = None
        self._edge_types = None

    @property
    def adjacency(self) -> dict[str, set[str]]:
        """Get adjacency map, building it if needed."""
        if self._adjacency is None:
            self._build_graph()
        return self._adjacency

    @property
    def edge_types(self) -> dict[tuple[str, str], EdgeType]:
        """Get edge types map, building it if needed."""
        if self._edge_types is None:
            self._build_graph()
        return self._edge_types

    def _build_graph(self):
        """Build adjacency and edge type maps from the plan."""
        adjacency: dict[str, set[str]] = {}
        edge_types: dict[tuple[str, str], EdgeType] = {}

        # Initialize all nodes
        for step in self.plan.steps:
            adjacency[step.uid] = set()

        # Add dependency edges (parent -> child)
        for child in self.plan.steps:
            for parent_uid in child.after:
                if parent_uid in adjacency:  # Skip invalid references
                    adjacency[parent_uid].add(child.uid)
                    edge_types[(parent_uid, child.uid)] = EdgeType.AFTER

        # Add branch edges
        for step in self.plan.steps:
            if hasattr(step, "branches") and step.branches:
                for target_uid in step.branches.values():
                    if target_uid in adjacency:  # Validate target exists
                        adjacency[step.uid].add(target_uid)
                        edge_types[(step.uid, target_uid)] = EdgeType.BRANCH

        self._adjacency = adjacency
        self._edge_types = edge_types

    def get_terminal_nodes(self) -> set[str]:
        """Get nodes with no outgoing edges."""
        return {node for node, neighbors in self.adjacency.items() if not neighbors}

    def get_root_nodes(self) -> set[str]:
        """Get nodes with no incoming dependencies."""
        incoming = {target for targets in self.adjacency.values() for target in targets}
        return set(self.adjacency) - incoming
