from dataclasses import dataclass
from enum import Enum
from typing import List


class Identifier(str, Enum):
    """Machine-readable key for the Final Answer node."""

    TYPE = "final_answer_node"


@dataclass(frozen=True)
class Meta:
    name: str
    description: str
    tags: List[str]


META = Meta(
    name="Final Answer Node",
    description="Outputs the final response",
    tags=["node", "final", "answer", "response", "output"],
)
