from flareward.programs.graph.graph_plan import GraphPlan
from flareward.programs.graph.topology.path_algorithms import (
    PathEnumerator as TopologyPathEnumerator,
)


class PathEnumerator:
    """Enumerates all possible execution paths through a graph."""

    def enumerate_paths(self, plan: GraphPlan) -> dict[str, list[str]]:
        """Generate all execution paths through the graph."""
        # Use topology utilities for path enumeration
        topology_enumerator = TopologyPathEnumerator(plan)
        return topology_enumerator.enumerate_paths()
