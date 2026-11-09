from dataclasses import dataclass
from enum import Enum
from typing import List


class Identifier(str, Enum):
    """Machine-readable key for the Mock Agent node."""

    TYPE = "mock_agent_node"


@dataclass(frozen=True)
class Meta:
    name: str
    description: str
    tags: List[str]


META = Meta(
    name="Mock Agent Node",
    description="Returns mock responses for testing",
    tags=["agent", "node", "mock", "test", "response"],
)
