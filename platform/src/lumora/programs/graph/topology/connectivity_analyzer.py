"""
Connectivity analysis for GraphPlan objects.

Clean OOP design for connectivity analysis.
"""

from typing import Set

from lumora.programs.graph.graph_plan import GraphPlan
from lumora.programs.graph.topology.graph_builder import GraphAnalyzer


class ConnectivityAnalyzer:
    """
    Connectivity analyzer that works with GraphPlan objects.

    Clean interface for connectivity analysis operations.
    """

    def __init__(self, plan: "GraphPlan"):
        self.analyzer = GraphAnalyzer(plan)

    def find_connected_nodes(self) -> Set[str]:
        """Find all nodes that have connections (incoming or outgoing)."""
        connected = set()

        # Nodes with outgoing connections
        for node, successors in self.analyzer.adjacency.items():
            if successors:
                connected.add(node)
                connected.update(successors)

        # Build reverse map to find nodes with incoming connections
        reverse_adjacency = {}
        for node in self.analyzer.adjacency:
            reverse_adjacency[node] = set()

        for node, successors in self.analyzer.adjacency.items():
            for successor in successors:
                if successor in reverse_adjacency:
                    reverse_adjacency[successor].add(node)

        # Nodes with incoming connections
        for node, predecessors in reverse_adjacency.items():
            if predecessors:
                connected.add(node)
                connected.update(predecessors)

        return connected

    def find_orphaned_nodes(self) -> Set[str]:
        """Find orphaned nodes with no connections."""
        all_nodes = set(self.analyzer.adjacency.keys())
        connected_nodes = self.find_connected_nodes()
        return all_nodes - connected_nodes
