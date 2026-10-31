from dataclasses import dataclass
from enum import StrEnum


class Identifier(StrEnum):
    """Machine-readable key for the Router Direct condition."""

    TYPE = "router_direct"


@dataclass(frozen=True)
class Meta:
    name: str
    description: str
    tags: list[str]


META = Meta(
    name="Router Direct",
    description="Reads target_branch from state and returns it directly for branching",
    tags=["router_direct", "condition", "branch", "target", "direct"],
)
