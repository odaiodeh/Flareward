"""
Cycle detection for GraphPlan objects.

Clean OOP design for cycle analysis.
"""

from collections import deque
from typing import List, Set

from lumora.programs.graph.graph_plan import GraphPlan
from lumora.programs.graph.topology.graph_builder import EdgeType, GraphAnalyzer
from lumora.programs.graph.topology.models import CycleInfo


class CycleDetector:
    """
    Cycle detector that works with GraphPlan objects.

    Clean interface for cycle detection operations.
    """

    def __init__(self, plan: "GraphPlan"):
        self.analyzer = GraphAnalyzer(plan)

    def detect_all_cycles(self) -> List[CycleInfo]:
        """Detect all cycles in the graph."""
        cycles = []
        visited = set()
        rec_stack = set()

        for node in self.analyzer.adjacency:
            if node not in visited:
                found_cycles = self._dfs_cycle_detection(node, visited, rec_stack, [])
                cycles.extend(found_cycles)

        return cycles

    def _dfs_cycle_detection(
        self, node: str, visited: Set[str], rec_stack: Set[str], path: List[str]
    ) -> List[CycleInfo]:
        """DFS-based cycle detection."""
        visited.add(node)
        rec_stack.add(node)
        current_path = path + [node]
        cycles = []

        for neighbor in self.analyzer.adjacency.get(node, set()):
            if neighbor not in visited:
                cycles.extend(self._dfs_cycle_detection(neighbor, visited, rec_stack, current_path))
            elif neighbor in rec_stack:
                # Found cycle - extract cycle path
                try:
                    cycle_start_idx = current_path.index(neighbor)
                    cycle_path = current_path[cycle_start_idx:] + [neighbor]
                    cycles.append(CycleInfo(cycle_path=cycle_path))
                except ValueError:
                    # Handle edge case where neighbor not in current path
                    cycle_path = current_path + [neighbor]
                    cycles.append(CycleInfo(cycle_path=cycle_path))

        rec_stack.remove(node)
        return cycles

    def is_dangerous_cycle(self, cycle: CycleInfo) -> bool:
        """
        Determine if a cycle is dangerous (inescapable or unconditional).

        A cycle is DANGEROUS if:
        1. ALL edges in cycle are AFTER (pure unconditional loop), OR
        2. No structural escape path to terminal nodes exists

        A cycle is SAFE if:
        - Has at least one BRANCH edge AND
        - At least one node in cycle has a path to a terminal node
        """
        # Normalize cycle path (last element duplicates the first)
        path = cycle.cycle_path
        if len(path) > 1 and path[0] == path[-1]:
            path = path[:-1]

        cycle_nodes = set(path)

        # Collect all edges in the cycle
        cycle_edges = []
        for u, v in zip(path, path[1:] + [path[0]]):
            edge_type = self.analyzer.edge_types.get((u, v))
            if edge_type:
                cycle_edges.append(edge_type)

        # Rule 1: ALL edges are AFTER → guaranteed infinite loop
        if cycle_edges and all(edge == EdgeType.AFTER for edge in cycle_edges):
            return True  # 100% dangerous - pure unconditional cycle

        # Rule 2: Has at least one BRANCH → check for structural escape
        # BFS from cycle nodes to find if ANY can reach a terminal node
        return not self._cycle_has_exit(cycle_nodes)

    def _cycle_has_exit(self, cycle_nodes: Set[str]) -> bool:
        """
        Check if cycle has a structural escape path to terminal nodes.

        Uses BFS from all cycle nodes to find if ANY path leads to
        a terminal node (node with no outgoing edges).

        Note: This checks STRUCTURAL escape, not runtime behavior.
        A BRANCH edge means escape is POSSIBLE, even if not guaranteed.
        """
        terminal_nodes = self.analyzer.get_terminal_nodes()

        # Special case: if any cycle node IS a terminal, cycle can exit
        if cycle_nodes & terminal_nodes:
            return True

        queue = deque(cycle_nodes)
        visited = set(cycle_nodes)  # Start with cycle nodes as visited

        while queue:
            node = queue.popleft()
            for neighbor in self.analyzer.adjacency.get(node, set()):
                if neighbor in visited:
                    continue  # Already checked this path

                if neighbor in terminal_nodes:
                    return True  # Found escape path!

                visited.add(neighbor)
                queue.append(neighbor)

        return False  # No escape path found
