"""
Adjacency models for graph topology.

Clean Pydantic models for managing adjacent nodes in a SOLID way.
"""

from pydantic import BaseModel, Field

from lumora.elements.domain.cards import ElementCard


class AdjacentNodes(BaseModel):
    """
    Pydantic model for managing adjacent nodes.

    Provides a clean, type-safe interface for working with adjacent nodes
    instead of using raw Dict[str, ElementCard].
    """

    nodes: dict[str, ElementCard] = Field(
        default_factory=dict, description="Map of node UID to ElementCard"
    )

    class Config:
        frozen = True  # Immutable for safety

    def __len__(self) -> int:
        """Number of adjacent nodes."""
        return len(self.nodes)

    def __bool__(self) -> bool:
        """True if there are adjacent nodes."""
        return bool(self.nodes)

    def __iter__(self):
        """Iterate over node UIDs."""
        return iter(self.nodes)

    def __contains__(self, uid: str) -> bool:
        """Check if node UID exists."""
        return uid in self.nodes

    def get(self, uid: str) -> ElementCard | None:
        """Get node by UID, returns None if not found."""
        return self.nodes.get(uid)

    def get_card(self, uid: str) -> ElementCard:
        """Get node by UID, raises KeyError if not found."""
        return self.nodes[uid]

    def get_uids(self) -> set[str]:
        """Get all node UIDs."""
        return set(self.nodes.keys())

    def get_cards(self) -> list[ElementCard]:
        """Get all ElementCards."""
        return list(self.nodes.values())

    def items(self):
        """Iterate over (uid, card) pairs."""
        return self.nodes.items()

    def keys(self):
        """Get node UIDs."""
        return self.nodes.keys()

    def values(self):
        """Get ElementCards."""
        return self.nodes.values()

    def filter_by_capability(self, capability: str) -> AdjacentNodes:
        """Filter nodes by capability."""
        filtered = {
            uid: card
            for uid, card in self.nodes.items()
            if any(cap.name == capability for cap in card.capabilities)
        }
        return AdjacentNodes(nodes=filtered)

    def filter_by_type(self, type_key: str) -> AdjacentNodes:
        """Filter nodes by type."""
        filtered = {uid: card for uid, card in self.nodes.items() if card.type_key == type_key}
        return AdjacentNodes(nodes=filtered)

    def has_capability(self, capability: str) -> bool:
        """Check if any adjacent node has the given capability."""
        return any(
            any(cap.name == capability for cap in card.capabilities) for card in self.nodes.values()
        )

    def get_by_capability(self, capability: str) -> list[ElementCard]:
        """Get all nodes with the given capability."""
        return [
            card
            for card in self.nodes.values()
            if any(cap.name == capability for cap in card.capabilities)
        ]

    def to_dict(self) -> dict[str, ElementCard]:
        """Convert to plain dict for backward compatibility."""
        return dict(self.nodes)

    @classmethod
    def from_dict(cls, nodes_dict: dict[str, ElementCard]) -> AdjacentNodes:
        """Create from plain dict for backward compatibility."""
        return cls(nodes=nodes_dict)

    @classmethod
    def empty(cls) -> AdjacentNodes:
        """Create empty adjacent nodes."""
        return cls(nodes={})

    def add_node(self, uid: str, card: ElementCard) -> AdjacentNodes:
        """Add a node (returns new instance since frozen)."""
        new_nodes = dict(self.nodes)
        new_nodes[uid] = card
        return AdjacentNodes(nodes=new_nodes)

    def remove_node(self, uid: str) -> AdjacentNodes:
        """Remove a node (returns new instance since frozen)."""
        new_nodes = {k: v for k, v in self.nodes.items() if k != uid}
        return AdjacentNodes(nodes=new_nodes)
