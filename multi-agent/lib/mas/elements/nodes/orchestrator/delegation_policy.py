"""
Orchestrator-specific delegation policy.

The orchestrator has special delegation rules because it manages
completion flow programmatically via _route_to_finalizer().
"""

from mas.application.agents.delegation_policy import DelegationPolicy
from mas.graph.models import AdjacentNodes
from mas.graph.topology.models import StepTopology


class OrchestratorDelegationPolicy(DelegationPolicy):
    """
    Orchestrator-specific delegation policy.

    BUSINESS RULE:
    The orchestrator should NOT delegate work to nodes on finalization paths.

    RATIONALE:
    The orchestrator has a special responsibility: it manages the completion
    flow programmatically. When orchestration work completes, it:

    1. Calls _route_to_finalizer() to send results to finalization nodes
    2. Uses topology information to find the path to output
    3. Routes results automatically without LLM involvement

    If the LLM could create work items for finalization path nodes, it would
    create confusion and incorrect behavior:

    BAD EXAMPLES:
        - LLM creates "Synthesize results" work item, assigns to "finalize" node
          → Wrong! Finalize happens automatically after completion

        - LLM creates "Aggregate findings" work item, assigns to "aggregator" node
          → Wrong! Aggregator is part of post-completion flow

    CORRECT BEHAVIOR:
        - LLM creates "Search Jira" work item, assigns to "jira_agent" node
          → Correct! This is actual work to be done

        - When all work completes, orchestrator automatically routes to finalize
          → Correct! This is programmatic, not delegated work

    WHY THIS IS ORCHESTRATOR-SPECIFIC:
    Other agent types don't have this special routing behavior. A regular
    agent might legitimately want to send results to an aggregator node
    as part of its work. Only the orchestrator has the "manage completion
    flow programmatically" responsibility.

    SOLID COMPLIANCE:
    - Single Responsibility: Only filters based on finalization paths
    - Open/Closed: Can be extended (e.g., add more filtering rules)
    - Liskov Substitution: Can be used anywhere DelegationPolicy is expected
    - Interface Segregation: Inherits minimal interface from base class
    - Dependency Inversion: Depends on abstractions (StepTopology, AdjacentNodes)
    """

    def __init__(self, topology: StepTopology, adjacent_nodes: AdjacentNodes):
        """
        Initialize orchestrator delegation policy.

        Args:
            topology: Step topology with finalization path information
            adjacent_nodes: All adjacent nodes from graph structure
        """
        super().__init__(adjacent_nodes)
        self._topology = topology
        self._finalization_path_uids = self._compute_finalization_path_uids()

    def _compute_finalization_path_uids(self) -> set[str]:
        """
        Identify nodes on finalization paths.

        A node is on a finalization path if:
        1. It has ANY distance to a finalizer in the topology
        2. The topology.finalizer_paths.distances contains the node UID

        The distance value indicates how many hops to reach a finalizer:
        - distance=1: Direct finalizer (writes to Channel.OUTPUT)
        - distance=2: One hop to finalizer (e.g., aggregator → finalize)
        - distance=N: N-1 hops to finalizer

        ALL of these should be excluded from delegation because they're
        part of the completion flow.

        Example:
            orchestrator → worker (delegable, no path to finalizer)
            orchestrator → aggregator (distance=2, NOT delegable)
            orchestrator → finalize (distance=1, NOT delegable)

        Returns:
            Set of node UIDs that are on finalization paths
        """
        if not self._topology or not self._topology.finalizer_paths:
            return set()

        # Any node with a distance to finalizer is on a finalization path
        finalization_uids = set(self._topology.finalizer_paths.distances.keys())
        return finalization_uids

    def is_delegable(self, node_uid: str) -> bool:
        """
        Check if orchestrator can delegate work to this node.

        A node is delegable if:
        1. It is in the adjacent nodes (topology check)
        2. It is NOT on a finalization path (policy check)

        Args:
            node_uid: UID of the node to check

        Returns:
            False if node is on finalization path or not adjacent,
            True otherwise
        """
        # Not delegable if not adjacent
        if node_uid not in self._adjacent_nodes:
            return False

        # Not delegable if on finalization path (orchestrator policy)
        if node_uid in self._finalization_path_uids:
            return False

        return True

    def filter_delegable_nodes(self, adjacent_nodes: AdjacentNodes) -> AdjacentNodes:
        """
        Filter adjacent nodes per orchestrator policy.

        Overrides base implementation to add logging for filtered nodes.

        Args:
            adjacent_nodes: All adjacent nodes

        Returns:
            Filtered AdjacentNodes excluding finalization path nodes
        """
        # Use base class implementation
        delegable = super().filter_delegable_nodes(adjacent_nodes)
        return delegable

    def get_finalization_path_uids(self) -> set[str]:
        """
        Get UIDs of nodes on finalization paths.

        Exposed for debugging, logging, and testing purposes.

        Returns:
            Set of node UIDs that are on finalization paths
        """
        return self._finalization_path_uids.copy()
