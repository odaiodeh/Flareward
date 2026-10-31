"""Delegation policies for agent nodes."""

from abc import ABC, abstractmethod

from mas.graph.models import AdjacentNodes


class DelegationPolicy(ABC):
    """Abstract base class for agent delegation policies."""

    def __init__(self, adjacent_nodes: AdjacentNodes):
        """Initialize delegation policy."""
        self._adjacent_nodes = adjacent_nodes

    @abstractmethod
    def is_delegable(self, node_uid: str) -> bool:
        """Check if a specific node can receive delegated work."""
        pass

    def filter_delegable_nodes(self, adjacent_nodes: AdjacentNodes) -> AdjacentNodes:
        """Filter adjacent nodes to only those that can receive delegated work."""
        delegable_dict = {
            uid: card for uid, card in adjacent_nodes.items() if self.is_delegable(uid)
        }

        return AdjacentNodes.from_dict(delegable_dict)

    def get_delegable_node_uids(self) -> set[str]:
        """Get set of all delegable node UIDs."""
        return {uid for uid in self._adjacent_nodes.keys() if self.is_delegable(uid)}

    def get_non_delegable_node_uids(self) -> set[str]:
        """Get set of all non-delegable node UIDs."""
        return {uid for uid in self._adjacent_nodes.keys() if not self.is_delegable(uid)}

    def count_delegable_nodes(self) -> int:
        """Count how many nodes are delegable."""
        return len(self.get_delegable_node_uids())


class PermissiveDelegationPolicy(DelegationPolicy):
    """Permissive delegation policy - allows delegation to all adjacent nodes."""

    def is_delegable(self, node_uid: str) -> bool:
        """All adjacent nodes are delegable."""
        return node_uid in self._adjacent_nodes
