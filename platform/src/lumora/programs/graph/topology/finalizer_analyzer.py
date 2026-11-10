"""
Finalizer node analysis for graph topology.

Identifies nodes that can reach finalizers (nodes writing to Channel.OUTPUT).
"""

from typing import Dict, List, Set

from lumora.programs.graph.graph_plan import GraphPlan
from lumora.programs.graph.topology.graph_traversal import GraphTraversal
from lumora.programs.graph.topology.models import FinalizerPathInfo, StepTopology


class FinalizerAnalyzer:
    """
    Analyzes graph topology to find paths to finalizer nodes.

    A finalizer is a node that writes to Channel.OUTPUT.
    """

    def __init__(self, output_channel: str = "output"):
        """
        Initialize analyzer.

        Args:
            output_channel: Name of the channel that finalizers write to.
                           Defaults to "output" (Channel.OUTPUT).
        """
        self._output_channel = output_channel

    def analyze_node_topology(
        self, plan: GraphPlan, from_node_uid: str, adjacent_node_uids: List[str]
    ) -> StepTopology:
        """
        Analyze topology for a specific node and its adjacents.

        Args:
            plan: The graph plan to analyze
            from_node_uid: The node we're analyzing from (e.g., orchestrator)
            adjacent_node_uids: UIDs of adjacent nodes to analyze

        Returns:
            StepTopology with finalizer distances
        """
        adjacency = GraphTraversal.build_adjacency(plan.steps)
        finalizer_distances = self._compute_finalizer_distances(
            plan, adjacency, from_node_uid, adjacent_node_uids
        )

        # Create FinalizerPathInfo if we have any distances
        finalizer_paths = None
        if finalizer_distances:
            finalizer_paths = FinalizerPathInfo(distances=finalizer_distances)

        return StepTopology(finalizer_paths=finalizer_paths)

    def _compute_finalizer_distances(
        self,
        plan: GraphPlan,
        adjacency: Dict[str, Set[str]],
        from_node_uid: str,
        adjacent_node_uids: List[str],
    ) -> Dict[str, int]:
        """
        Compute distances from adjacent nodes to nearest finalizers.

        Excludes paths that cycle back through the from_node.

        Args:
            plan: Graph plan for looking up step details
            adjacency: Pre-built adjacency map
            from_node_uid: The originating node (to exclude cycles through)
            adjacent_node_uids: Adjacent nodes to compute distances for

        Returns:
            Dict mapping adjacent node UID to distance to nearest finalizer
        """
        results: Dict[str, int] = {}

        # Create predicate for finalizer detection
        def is_finalizer(node_uid: str) -> bool:
            step = plan.get_step(node_uid)
            if not step:
                return False
            # Check if node writes to output channel
            return self._output_channel in step.total_writes()

        # For each adjacent node, find distance to nearest finalizer
        for adj_uid in adjacent_node_uids:
            if adj_uid not in adjacency:
                continue

            # If adjacent node itself is a finalizer
            if is_finalizer(adj_uid):
                results[adj_uid] = 1
                continue

            # BFS from adjacent node, excluding paths back through from_node
            distance = GraphTraversal.find_shortest_distance(
                start=adj_uid,
                adjacency=adjacency,
                predicate=is_finalizer,
                exclude_nodes={from_node_uid},  # Prevent cycles back through originator
            )

            if distance is not None:
                # Add 1 for the hop from from_node to adj_node
                results[adj_uid] = distance + 1

        return results

    def find_all_finalizers(self, plan: GraphPlan) -> Set[str]:
        """
        Find all finalizer nodes in the graph.

        Args:
            plan: Graph plan to analyze

        Returns:
            Set of UIDs for all nodes that write to output channel
        """
        finalizers = set()

        for step in plan.steps:
            if self._output_channel in step.total_writes():
                finalizers.add(step.uid)

        return finalizers
