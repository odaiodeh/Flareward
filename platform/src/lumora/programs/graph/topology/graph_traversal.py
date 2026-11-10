"""
Pure graph traversal utilities.

No domain knowledge, just graph algorithms.
SOLID: Single responsibility for graph traversal operations.
"""

from collections import deque
from typing import Callable, Dict, List, Optional, Set

from lumora.programs.graph.models import Step


class GraphTraversal:
    """
    Static utility class for graph traversal algorithms.

    Pure functions with no state or domain knowledge.
    """

    @staticmethod
    def build_adjacency(steps: List["Step"]) -> Dict[str, Set[str]]:
        """
        Build adjacency map from step dependencies.

        Args:
            steps: List of Step objects with 'after' and 'branches' attributes

        Returns:
            Dict mapping step UID to set of adjacent (successor) UIDs
        """
        adjacency: Dict[str, Set[str]] = {}

        # Initialize all nodes
        for step in steps:
            adjacency[step.uid] = set()

        # Add dependency edges (parent -> child)
        for child in steps:
            for parent_uid in child.after:
                if parent_uid in adjacency:  # Skip invalid references
                    adjacency[parent_uid].add(child.uid)

        # Add branch edges
        for step in steps:
            if hasattr(step, "branches") and step.branches:
                for target_uid in step.branches.values():
                    if target_uid in adjacency:  # Validate target exists
                        adjacency[step.uid].add(target_uid)

        return adjacency

    @staticmethod
    def find_reachable_nodes(
        start: str,
        adjacency: Dict[str, Set[str]],
        predicate: Callable[[str], bool],
        exclude_nodes: Optional[Set[str]] = None,
    ) -> Dict[str, int]:
        """
        BFS to find all nodes matching predicate with their distances.

        Args:
            start: Starting node UID
            adjacency: Adjacency map (node -> set of successors)
            predicate: Function to test if a node matches criteria
            exclude_nodes: Nodes to exclude from traversal (e.g., to prevent cycles)

        Returns:
            Dict mapping matching node UIDs to their distance from start
        """
        if start not in adjacency:
            return {}

        exclude_nodes = exclude_nodes or set()
        results: Dict[str, int] = {}

        # Check if start node itself matches
        if predicate(start) and start not in exclude_nodes:
            results[start] = 0

        # BFS for other matching nodes
        queue = deque([(start, 0)])
        visited = {start}

        while queue:
            current, distance = queue.popleft()

            for neighbor in adjacency.get(current, set()):
                if neighbor in visited or neighbor in exclude_nodes:
                    continue

                visited.add(neighbor)
                new_distance = distance + 1

                if predicate(neighbor):
                    results[neighbor] = new_distance

                queue.append((neighbor, new_distance))

        return results

    @staticmethod
    def find_shortest_distance(
        start: str,
        adjacency: Dict[str, Set[str]],
        predicate: Callable[[str], bool],
        exclude_nodes: Optional[Set[str]] = None,
    ) -> Optional[int]:
        """
        Find shortest distance to any node matching predicate.

        Args:
            start: Starting node UID
            adjacency: Adjacency map
            predicate: Function to test if a node matches criteria
            exclude_nodes: Nodes to exclude from traversal

        Returns:
            Shortest distance to a matching node, or None if no path exists
        """
        reachable = GraphTraversal.find_reachable_nodes(start, adjacency, predicate, exclude_nodes)

        if not reachable:
            return None

        return min(reachable.values())
