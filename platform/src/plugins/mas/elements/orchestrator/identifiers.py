from dataclasses import dataclass
from enum import Enum
from typing import List


class Identifier(str, Enum):
    """Machine-readable key for the Orchestrator node."""

    TYPE = "orchestrator_node"


@dataclass(frozen=True)
class Meta:
    """Human-readable metadata about the element."""

    name: str
    description: str
    tags: List[str]


META = Meta(
    name="Orchestrator Node",
    description="Orchestrator node that plans work, delegates to adjacent nodes, and synthesizes results",
    tags=[
        "orchestrator",
        "node",
        "planning",
        "delegation",
        "coordination",
        "workplan",
        "multi-agent",
    ],
)
