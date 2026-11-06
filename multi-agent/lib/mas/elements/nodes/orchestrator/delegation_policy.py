"""Graph topology supplies the orchestrator's explicit delegation exclusions."""

from mas.application.agents.delegation_policy import DelegationPolicy
from mas.graph.models import AdjacentNodes
from mas.graph.topology.models import StepTopology


class OrchestratorDelegationPolicy(DelegationPolicy):
    """Finalization is routed by the orchestrator rather than delegated as work."""

    def __init__(self, topology: StepTopology, adjacent_nodes: AdjacentNodes) -> None:
        super().__init__(adjacent_nodes.get_uids())
        self._finalization_path_uids = frozenset(
            topology.finalizer_paths.distances if topology.finalizer_paths else ()
        )

    def is_delegable(self, node_uid: str) -> bool:
        return node_uid in self._candidates and node_uid not in self._finalization_path_uids
