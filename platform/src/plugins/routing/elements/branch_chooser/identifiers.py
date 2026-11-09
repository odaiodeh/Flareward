from dataclasses import dataclass
from enum import Enum
from typing import List


class Identifier(str, Enum):
    """Machine-readable key for the Branch Chooser node."""

    TYPE = "branch_chooser_node"


@dataclass(frozen=True)
class Meta:
    name: str
    description: str
    tags: List[str]


META = Meta(
    name="Branch Chooser Node",
    description="Chooses the first target branch from step context and writes it to target_branch state channel",
    tags=["branch", "node", "mock", "chooser", "target"],
)
