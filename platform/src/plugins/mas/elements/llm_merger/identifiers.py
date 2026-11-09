from dataclasses import dataclass
from enum import Enum
from typing import List


class Identifier(str, Enum):
    """Machine-readable key for the LLM Merger node."""

    TYPE = "merger_node"


@dataclass(frozen=True)
class Meta:
    name: str
    description: str
    tags: List[str]


META = Meta(
    name="Merger Node",
    description="Aggregates and synthesizes agent outputs",
    tags=["node", "merger", "llm", "aggregation", "synthesis"],
)
